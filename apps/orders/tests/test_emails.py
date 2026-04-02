import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.core import mail
from django.test import override_settings


def make_mock_order(payment_attempts=1, payment_method="pix"):
    buyer = MagicMock()
    buyer.email = "buyer@example.com"
    buyer.first_name = "João"

    event = MagicMock()
    event.title = "Show de Verão"

    order = MagicMock()
    order.id = uuid.uuid4()
    order.reference = "TT-20260401-ABCD12"
    order.buyer = buyer
    order.event = event
    order.grand_total = Decimal("150.00")
    order.payment_method = payment_method
    order.payment_attempts = payment_attempts
    order.expires_at = __import__("datetime").datetime(2026, 4, 1, 18, 0, 0, tzinfo=__import__("datetime").timezone.utc)
    return order


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="TicketTchê <noreply@tickettche.local>",
)
@pytest.mark.django_db
def test_send_payment_failed_email_renders_html():
    from apps.orders.emails import send_payment_failed_email

    order = make_mock_order(payment_attempts=1, payment_method="pix")
    send_payment_failed_email(order)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]

    assert "Show de Verão" in msg.subject
    assert msg.to == ["buyer@example.com"]
    assert msg.from_email == "TicketTchê <noreply@tickettche.local>"

    # Check HTML alternative
    html_bodies = [body for body, mime in msg.alternatives if mime == "text/html"]
    assert html_bodies, "No HTML alternative found"
    html = html_bodies[0]

    assert "João" in html
    assert "Show de Verão" in html
    assert "TT-20260401-ABCD12" in html
    assert "PIX" in html
    assert "Tentar Novamente" in html
    assert f"http://localhost:3000/orders/{order.id}/pay" in html


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="TicketTchê <noreply@tickettche.local>",
)
@pytest.mark.django_db
def test_send_payment_failed_email_attempts_limit():
    from apps.orders.emails import send_payment_failed_email

    order = make_mock_order(payment_attempts=5, payment_method="credit_card")
    send_payment_failed_email(order)

    assert len(mail.outbox) == 1
    html_bodies = [body for body, mime in mail.outbox[0].alternatives if mime == "text/html"]
    html = html_bodies[0]

    assert "Tentar Novamente" not in html
    assert "limite de tentativas" in html
    assert "Cartão de Crédito" in html


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="TicketTchê <noreply@tickettche.local>",
)
@pytest.mark.django_db
def test_send_pending_order_reminder_email_renders():
    from apps.orders.emails import send_pending_order_reminder_email

    order = make_mock_order()
    send_pending_order_reminder_email(order)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]

    assert "Show de Verão" in msg.subject
    assert msg.to == ["buyer@example.com"]

    html_bodies = [body for body, mime in msg.alternatives if mime == "text/html"]
    assert html_bodies
    html = html_bodies[0]

    assert "João" in html
    assert "Show de Verão" in html
    assert "TT-20260401-ABCD12" in html
    assert "Completar Pagamento" in html
    assert f"http://localhost:3000/orders/{order.id}/pay" in html
