import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers as drf_serializers

from apps.companies.models import Company
from apps.orders.models import Order

from .models import Withdrawal

logger = logging.getLogger(__name__)

WITHDRAWAL_HOLD_DAYS = 7
MINIMUM_WITHDRAWAL = Decimal("10.00")
MAXIMUM_SINGLE_WITHDRAWAL = Decimal("2000.00")
DAILY_WITHDRAWAL_LIMIT = Decimal("5000.00")


def get_company_balance(company_id: str) -> dict:
    """
    Calculate current balance breakdown for a company.

    available_balance: earned from events that ended >7 days ago, minus
                       withdrawals already submitted (pending/processing/completed).
    pending_balance:   earned from events that ended <=7 days ago (not yet withdrawable).
    total_earned:      all-time sum of paid order totals for the company's events.
    total_withdrawn:   sum of completed withdrawals.
    """
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        raise drf_serializers.ValidationError({"company_id": "Empresa não encontrada."})

    cutoff = timezone.now() - timedelta(days=WITHDRAWAL_HOLD_DAYS)

    paid_orders = Order.objects.filter(
        event__company=company,
        status=Order.Status.PAID,
    )

    total_earned = paid_orders.aggregate(s=Sum("total"))["s"] or Decimal("0.00")

    available_earned = (
        paid_orders.filter(event__end_date__lt=cutoff).aggregate(s=Sum("total"))["s"]
        or Decimal("0.00")
    )

    pending_earned = (
        paid_orders.filter(event__end_date__gte=cutoff).aggregate(s=Sum("total"))["s"]
        or Decimal("0.00")
    )

    already_withdrawn = (
        Withdrawal.objects.filter(
            company=company,
            status__in=[
                Withdrawal.Status.PENDING,
                Withdrawal.Status.PROCESSING,
                Withdrawal.Status.COMPLETED,
            ],
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )

    total_withdrawn = (
        Withdrawal.objects.filter(
            company=company,
            status=Withdrawal.Status.COMPLETED,
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )

    available_balance = max(available_earned - already_withdrawn, Decimal("0.00"))

    return {
        "available_balance": available_balance,
        "pending_balance": pending_earned,
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
    }


def request_withdrawal(company, user, amount: Decimal, pix_key: str, pix_key_type: str):
    """
    Create a new withdrawal request after validating amount against available balance.
    SECURITY (FINDING-013): Daily limit, per-request cap, and audit logging.
    """
    balance = get_company_balance(str(company.id))

    if amount < MINIMUM_WITHDRAWAL:
        raise drf_serializers.ValidationError(
            {"amount": f"Valor mínimo para saque é R${MINIMUM_WITHDRAWAL}."}
        )

    if amount > MAXIMUM_SINGLE_WITHDRAWAL:
        raise drf_serializers.ValidationError(
            {"amount": f"Valor máximo por saque é R${MAXIMUM_SINGLE_WITHDRAWAL}. Para valores maiores, entre em contato com o suporte."}
        )

    if amount > balance["available_balance"]:
        raise drf_serializers.ValidationError(
            {
                "amount": (
                    f"Saldo disponível insuficiente. "
                    f"Disponível: R${balance['available_balance']:.2f}."
                )
            }
        )

    # SECURITY FIX (FINDING-013): Daily withdrawal limit
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_total = (
        Withdrawal.objects.filter(
            company=company,
            created_at__gte=today_start,
            status__in=[
                Withdrawal.Status.PENDING,
                Withdrawal.Status.PROCESSING,
                Withdrawal.Status.COMPLETED,
            ],
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )
    if daily_total + amount > DAILY_WITHDRAWAL_LIMIT:
        raise drf_serializers.ValidationError(
            {
                "amount": (
                    f"Limite diário de saques é R${DAILY_WITHDRAWAL_LIMIT}. "
                    f"Já solicitado hoje: R${daily_total:.2f}."
                )
            }
        )

    withdrawal = Withdrawal.objects.create(
        company=company,
        requested_by=user,
        amount=amount,
        pix_key=pix_key,
        pix_key_type=pix_key_type,
        status=Withdrawal.Status.PENDING,
    )

    logger.info(
        "Withdrawal requested: id=%s company=%s amount=%s user=%s daily_total=%s",
        withdrawal.id,
        company.id,
        amount,
        user.email,
        daily_total + amount,
    )

    return withdrawal


def process_withdrawal(withdrawal_id: str):
    """
    Attempt to send a PIX transfer via Mercado Pago for a PENDING withdrawal.
    Sets status to PROCESSING while the transfer is in-flight, or FAILED on error.
    A periodic Celery task polls for completion.
    """
    try:
        withdrawal = Withdrawal.objects.get(pk=withdrawal_id, status=Withdrawal.Status.PENDING)
    except Withdrawal.DoesNotExist:
        logger.warning("process_withdrawal: withdrawal %s not found or not PENDING", withdrawal_id)
        return None

    withdrawal.status = Withdrawal.Status.PROCESSING
    withdrawal.save(update_fields=["status", "updated_at"])

    try:
        transfer_id = _send_pix_transfer(
            amount=withdrawal.amount,
            pix_key=withdrawal.pix_key,
            pix_key_type=withdrawal.pix_key_type,
            reference=str(withdrawal.id),
        )
        withdrawal.mp_transfer_id = transfer_id or ""
        withdrawal.status = Withdrawal.Status.PROCESSING
        withdrawal.save(update_fields=["status", "mp_transfer_id", "updated_at"])
        logger.info("PIX transfer initiated: withdrawal=%s transfer_id=%s", withdrawal_id, transfer_id)
    except Exception as exc:
        withdrawal.status = Withdrawal.Status.FAILED
        withdrawal.failure_reason = str(exc)
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=["status", "failure_reason", "processed_at", "updated_at"])
        logger.error("PIX transfer failed: withdrawal=%s error=%s", withdrawal_id, exc)

    return withdrawal


# Mapeamento dos tipos de chave PIX do sistema para o formato esperado pela API do MP
_PIX_KEY_TYPE_MAP = {
    "cpf": "CPF",
    "email": "EMAIL",
    "phone": "PHONE",
    "random": "EVP",  # Chave aleatória = EVP (Endereço Virtual de Pagamento)
}


def _send_pix_transfer(amount: Decimal, pix_key: str, pix_key_type: str, reference: str) -> str:
    """
    Send money to an organizer via Mercado Pago PIX bank transfer.

    Works in both sandbox (TEST- token) and production (APP_USR- token).
    When neither is present (dev/placeholder credentials), logs the intent
    and returns a MANUAL- placeholder so the finance team can act manually.
    """
    import requests
    from django.conf import settings

    token: str = getattr(settings, "MP_ACCESS_TOKEN", "")

    is_sandbox = token.startswith("TEST-")
    is_production = token.startswith("APP_USR-")

    if not (is_sandbox or is_production):
        # Dev / unconfigured environment — log intent only
        logger.info(
            "PIX transfer skipped (no real MP credentials) — amount=R$%s key=%s (%s) ref=%s",
            amount, pix_key, pix_key_type, reference,
        )
        return f"MANUAL-{reference[:8]}"

    # Converte tipo de chave para o formato da API do MP (maiúsculo / EVP)
    mp_pix_key_type = _PIX_KEY_TYPE_MAP.get(pix_key_type, pix_key_type.upper())

    logger.info(
        "PIX transfer via MP — amount=R$%s key=%s (%s→%s) ref=%s env=%s",
        amount, pix_key, pix_key_type, mp_pix_key_type, reference,
        "sandbox" if is_sandbox else "production",
    )

    response = requests.post(
        "https://api.mercadopago.com/v1/account/bank_transfers",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": reference,
        },
        json={
            "transaction_amount": float(amount),
            "description": f"TicketTchê - Saque {reference}",
            "external_reference": reference,
            "payment_method": {
                "id": "pix",
            },
            "receiver": {
                "pix_key": pix_key,
                "pix_key_type": mp_pix_key_type,
            },
        },
        timeout=30,
    )

    try:
        data = response.json()
    except Exception:
        data = {}

    if not response.ok:
        error_msg = data.get("message") or data.get("error") or response.text
        raise RuntimeError(f"MP bank_transfers error {response.status_code}: {error_msg}")

    transfer_id = str(data.get("id", ""))
    logger.info("MP bank transfer created: id=%s ref=%s", transfer_id, reference)
    return transfer_id


def poll_transfer_status(withdrawal_id: str) -> None:
    """
    Query Mercado Pago for the current status of a PROCESSING withdrawal
    and update to COMPLETED or FAILED accordingly.

    Called by the periodic Celery task `poll_processing_withdrawals`.
    """
    import requests
    from django.conf import settings

    try:
        withdrawal = Withdrawal.objects.get(pk=withdrawal_id, status=Withdrawal.Status.PROCESSING)
    except Withdrawal.DoesNotExist:
        return

    if not withdrawal.mp_transfer_id or withdrawal.mp_transfer_id.startswith("MANUAL-"):
        # Manual transfer — não há como consultar no MP; deixa para a equipe financeira
        logger.info(
            "poll_transfer_status: withdrawal %s is manual (transfer_id=%s), skipping",
            withdrawal_id, withdrawal.mp_transfer_id,
        )
        return

    token: str = getattr(settings, "MP_ACCESS_TOKEN", "")
    if not (token.startswith("TEST-") or token.startswith("APP_USR-")):
        return  # Sem credenciais reais, nada a fazer

    try:
        response = requests.get(
            f"https://api.mercadopago.com/v1/account/bank_transfers/{withdrawal.mp_transfer_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = response.json() if response.ok else {}
    except Exception as exc:
        logger.warning("poll_transfer_status: HTTP error for withdrawal %s: %s", withdrawal_id, exc)
        return

    mp_status = data.get("status", "")

    if mp_status in ("approved", "settled"):
        withdrawal.status = Withdrawal.Status.COMPLETED
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=["status", "processed_at", "updated_at"])
        logger.info("Withdrawal COMPLETED: id=%s mp_transfer=%s", withdrawal_id, withdrawal.mp_transfer_id)

    elif mp_status in ("rejected", "cancelled", "refunded", "expired"):
        withdrawal.status = Withdrawal.Status.FAILED
        withdrawal.failure_reason = f"MP transfer status: {mp_status}"
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=["status", "failure_reason", "processed_at", "updated_at"])
        logger.warning(
            "Withdrawal FAILED: id=%s mp_transfer=%s mp_status=%s",
            withdrawal_id, withdrawal.mp_transfer_id, mp_status,
        )

    else:
        logger.debug(
            "poll_transfer_status: withdrawal %s still in progress (mp_status=%s)",
            withdrawal_id, mp_status,
        )
