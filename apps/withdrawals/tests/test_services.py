from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import serializers as drf_serializers

from apps.accounts.tests.factories import UserFactory
from apps.companies.tests.factories import CompanyFactory
from apps.events.tests.factories import EventFactory
from apps.orders.models import Order
from apps.orders.tests.factories import OrderFactory
from apps.withdrawals.models import Withdrawal
from apps.withdrawals.services import (
    approve_withdrawal,
    get_company_balance,
    process_withdrawal,
    reject_withdrawal,
    request_withdrawal,
    resolve_withdrawal,
)


def _company_with_earnings(amount="500.00"):
    """Company with a paid order for an event that ended >7 days ago."""
    company = CompanyFactory()
    event = EventFactory(
        company=company,
        start_date=timezone.now() - timedelta(days=20),
        end_date=timezone.now() - timedelta(days=15),
    )
    OrderFactory(
        event=event,
        status=Order.Status.PAID,
        total=Decimal(amount),
    )
    return company


@pytest.mark.django_db
class TestBalance:
    def test_available_after_hold_period(self):
        company = _company_with_earnings("500.00")
        balance = get_company_balance(str(company.id))
        assert balance["available_balance"] == Decimal("500.00")

    def test_recent_event_is_pending(self):
        company = CompanyFactory()
        event = EventFactory(
            company=company,
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(days=1),
        )
        OrderFactory(event=event, status=Order.Status.PAID, total=Decimal("300.00"))
        balance = get_company_balance(str(company.id))
        assert balance["available_balance"] == Decimal("0.00")
        assert balance["pending_balance"] == Decimal("300.00")

    def test_refunded_orders_do_not_count(self):
        company = CompanyFactory()
        event = EventFactory(
            company=company,
            start_date=timezone.now() - timedelta(days=20),
            end_date=timezone.now() - timedelta(days=15),
        )
        OrderFactory(event=event, status=Order.Status.REFUNDED, total=Decimal("300.00"))
        balance = get_company_balance(str(company.id))
        assert balance["available_balance"] == Decimal("0.00")


@pytest.mark.django_db
class TestRequestWithdrawal:
    def test_cannot_exceed_available_balance(self):
        company = _company_with_earnings("100.00")
        user = UserFactory()
        with pytest.raises(drf_serializers.ValidationError):
            request_withdrawal(company, user, Decimal("150.00"), "a@b.com", "email")

    def test_reserves_balance_while_pending(self):
        company = _company_with_earnings("500.00")
        user = UserFactory()
        request_withdrawal(company, user, Decimal("400.00"), "a@b.com", "email")
        with pytest.raises(drf_serializers.ValidationError):
            request_withdrawal(company, user, Decimal("200.00"), "a@b.com", "email")

    def test_rejected_withdrawal_frees_balance(self):
        company = _company_with_earnings("500.00")
        user = UserFactory()
        admin = UserFactory(role="admin")
        w = request_withdrawal(company, user, Decimal("400.00"), "a@b.com", "email")
        reject_withdrawal(str(w.id), admin, "dados incorretos")
        balance = get_company_balance(str(company.id))
        assert balance["available_balance"] == Decimal("500.00")


@pytest.mark.django_db
class TestApprovalFlow:
    def test_pending_is_never_processed_automatically(self):
        company = _company_with_earnings()
        user = UserFactory()
        w = request_withdrawal(company, user, Decimal("100.00"), "a@b.com", "email")
        result = process_withdrawal(str(w.id))
        assert result is None
        w.refresh_from_db()
        assert w.status == Withdrawal.Status.PENDING

    def test_approve_then_process(self):
        company = _company_with_earnings()
        user = UserFactory()
        admin = UserFactory(role="admin")
        w = request_withdrawal(company, user, Decimal("100.00"), "a@b.com", "email")

        approve_withdrawal(str(w.id), admin)
        w.refresh_from_db()
        assert w.status == Withdrawal.Status.APPROVED
        assert w.reviewed_by == admin

        with patch(
            "apps.withdrawals.services._send_pix_transfer", return_value="MP-123"
        ) as mock_transfer:
            process_withdrawal(str(w.id))
        mock_transfer.assert_called_once()
        w.refresh_from_db()
        assert w.status == Withdrawal.Status.PROCESSING
        assert w.mp_transfer_id == "MP-123"

    def test_double_approve_blocked(self):
        company = _company_with_earnings()
        user = UserFactory()
        admin = UserFactory(role="admin")
        w = request_withdrawal(company, user, Decimal("100.00"), "a@b.com", "email")
        approve_withdrawal(str(w.id), admin)
        with pytest.raises(drf_serializers.ValidationError):
            approve_withdrawal(str(w.id), admin)

    def test_resolve_manual_processing(self):
        company = _company_with_earnings()
        user = UserFactory()
        admin = UserFactory(role="admin")
        w = request_withdrawal(company, user, Decimal("100.00"), "a@b.com", "email")
        Withdrawal.objects.filter(pk=w.pk).update(
            status=Withdrawal.Status.PROCESSING, mp_transfer_id="MANUAL-abc"
        )
        resolve_withdrawal(str(w.id), admin, Withdrawal.Status.COMPLETED)
        w.refresh_from_db()
        assert w.status == Withdrawal.Status.COMPLETED

    def test_transfer_failure_marks_failed(self):
        company = _company_with_earnings()
        user = UserFactory()
        admin = UserFactory(role="admin")
        w = request_withdrawal(company, user, Decimal("100.00"), "a@b.com", "email")
        approve_withdrawal(str(w.id), admin)
        with patch(
            "apps.withdrawals.services._send_pix_transfer",
            side_effect=RuntimeError("MP error"),
        ):
            process_withdrawal(str(w.id))
        w.refresh_from_db()
        assert w.status == Withdrawal.Status.FAILED
