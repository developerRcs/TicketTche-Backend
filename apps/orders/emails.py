from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

PAYMENT_METHOD_LABELS = {
    "pix": "PIX",
    "credit_card": "Cartão de Crédito",
    "debit_card": "Cartão de Débito",
}

MAX_PAYMENT_ATTEMPTS = 5


def send_payment_failed_email(order):
    """Send email when payment fails. order.buyer must be loaded."""
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    retry_url = f"{frontend_url}/orders/{order.id}/pay"

    context = {
        "first_name": order.buyer.first_name,
        "event_title": order.event.title,
        "reference": order.reference,
        "grand_total": order.grand_total,
        "payment_method": PAYMENT_METHOD_LABELS.get(order.payment_method, order.payment_method),
        "payment_attempts": order.payment_attempts,
        "max_attempts": MAX_PAYMENT_ATTEMPTS,
        "retry_url": retry_url,
        "attempts_exceeded": order.payment_attempts >= MAX_PAYMENT_ATTEMPTS,
    }

    subject = f"Pagamento não processado — {order.event.title}"
    html_body = render_to_string("orders/emails/payment_failed.html", context)
    text_body = (
        f"Olá, {context['first_name']}!\n\n"
        f"Seu pagamento para {context['event_title']} não foi processado.\n"
        f"Pedido: {context['reference']}\n"
        f"Valor: R$ {context['grand_total']}\n"
        f"Tentativa {context['payment_attempts']} de {MAX_PAYMENT_ATTEMPTS}\n\n"
        + (
            f"Tente novamente: {retry_url}"
            if not context["attempts_exceeded"]
            else "Você atingiu o limite de tentativas. Entre em contato com suporte."
        )
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.buyer.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()


def send_pending_order_reminder_email(order):
    """Send reminder email for orders pending > 2 hours."""
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    retry_url = f"{frontend_url}/orders/{order.id}/pay"

    from django.utils import timezone as tz
    expires_at_formatted = order.expires_at.strftime("%d/%m/%Y %H:%M")

    context = {
        "first_name": order.buyer.first_name,
        "event_title": order.event.title,
        "reference": order.reference,
        "grand_total": order.grand_total,
        "expires_at_formatted": expires_at_formatted,
        "retry_url": retry_url,
    }

    subject = f"Seu pedido está aguardando pagamento — {order.event.title}"
    html_body = render_to_string("orders/emails/pending_order.html", context)
    text_body = (
        f"Olá, {context['first_name']}!\n\n"
        f"Você tem um pedido aguardando pagamento para {context['event_title']}.\n"
        f"Pedido: {context['reference']}\n"
        f"Valor: R$ {context['grand_total']}\n"
        f"Expira em: {expires_at_formatted}\n\n"
        f"Complete o pagamento: {retry_url}"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.buyer.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()
