"""
Serviço de recuperação de senha.

Fluxo:
  1. request_password_reset(email) → gera token UUID, armazena em Redis TTL 30min, envia email
  2. validate_reset_token(token) → verifica existência no Redis
  3. confirm_password_reset(token, new_password) → valida, troca senha, envia código de confirmação
"""
import random
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from rest_framework import serializers

from .models import CustomUser

# Prefixos de chave Redis
_TOKEN_PREFIX = "pwd_reset_token:"
_USER_PREFIX  = "pwd_reset_user:"

# TTL 30 minutos
_TTL_SECONDS = 30 * 60

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://tickettche.com.br")


def _generate_token() -> str:
    return secrets.token_urlsafe(48)


def _generate_confirmation_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def request_password_reset(email: str) -> None:
    """
    Solicita redefinição de senha.
    Sempre retorna sem revelar se o email existe (prevenção de user enumeration).
    """
    try:
        user = CustomUser.objects.get(email=email, is_active=True)
    except CustomUser.DoesNotExist:
        return  # Silencioso — não revela se email existe

    # Invalida token anterior caso existam (um token por usuário por vez)
    old_token_key = _USER_PREFIX + str(user.pk)
    old_token = cache.get(old_token_key)
    if old_token:
        cache.delete(_TOKEN_PREFIX + old_token)

    token = _generate_token()
    reset_url = f"{FRONTEND_URL}/redefinir-senha/{token}"

    # Armazena: token → user_id e user_id → token (para invalidar anterior)
    ttl = timedelta(seconds=_TTL_SECONDS)
    cache.set(_TOKEN_PREFIX + token, str(user.pk), timeout=_TTL_SECONDS)
    cache.set(old_token_key, token, timeout=_TTL_SECONDS)

    _send_reset_email(user, reset_url, ttl)


def validate_reset_token(token: str) -> bool:
    """Retorna True se o token ainda é válido."""
    return cache.get(_TOKEN_PREFIX + token) is not None


def confirm_password_reset(token: str, new_password: str) -> None:
    """
    Confirma a troca de senha.
    Raises ValidationError se token inválido/expirado.
    """
    user_id = cache.get(_TOKEN_PREFIX + token)
    if not user_id:
        raise serializers.ValidationError(
            {"token": "Link de redefinição inválido ou expirado. Solicite um novo."}
        )

    try:
        user = CustomUser.objects.get(pk=user_id, is_active=True)
    except CustomUser.DoesNotExist:
        raise serializers.ValidationError(
            {"token": "Usuário não encontrado."}
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])

    # Invalida token (one-time use)
    cache.delete(_TOKEN_PREFIX + token)
    cache.delete(_USER_PREFIX + str(user.pk))

    # Envia email de confirmação com código de 6 dígitos
    code = _generate_confirmation_code()
    _send_confirmation_email(user, code)


# ── Emails ──────────────────────────────────────────────────────────────────

def _send_reset_email(user: CustomUser, reset_url: str, ttl: timedelta) -> None:
    minutes = int(ttl.total_seconds() // 60)
    context = {
        "user": user,
        "reset_url": reset_url,
        "validity_minutes": minutes,
    }
    subject = "Redefinição de senha — TicketTchê"
    html_body = render_to_string("accounts/emails/password_reset_request.html", context)
    text_body = (
        f"Olá {user.first_name or 'usuário'},\n\n"
        f"Para redefinir sua senha, acesse o link abaixo (válido por {minutes} minutos):\n\n"
        f"{reset_url}\n\n"
        "Se você não solicitou a troca de senha, ignore este email.\n\n"
        "— TicketTchê"
    )
    _send_email(subject, text_body, html_body, [user.email])


def _send_confirmation_email(user: CustomUser, code: str) -> None:
    context = {
        "user": user,
        "confirmation_code": code,
    }
    subject = "Senha alterada com sucesso — TicketTchê"
    html_body = render_to_string("accounts/emails/password_reset_confirm.html", context)
    text_body = (
        f"Olá {user.first_name or 'usuário'},\n\n"
        f"Sua senha foi redefinida com sucesso.\n\n"
        f"Código de confirmação: {code}\n\n"
        "Se você não fez esta alteração, entre em contato imediatamente: suporte@tickettche.com.br\n\n"
        "— TicketTchê"
    )
    _send_email(subject, text_body, html_body, [user.email])


def _send_email(subject: str, text_body: str, html_body: str, recipients: list) -> None:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@tickettche.com.br"),
        to=recipients,
    )
    msg.attach_alternative(html_body, "text/html")
    try:
        msg.send(fail_silently=False)
    except Exception:
        # Não bloqueia a resposta da API por falha de email
        import logging
        logging.getLogger(__name__).error(
            "Failed to send password reset email to %s", recipients, exc_info=True
        )
