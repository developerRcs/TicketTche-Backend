import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.tickets.models import Ticket, TicketTransfer
from apps.tickets.tests.factories import TicketFactory, TicketTransferFactory


@pytest.mark.django_db
class TestExpirePendingTransfers:
    def test_expire_pending_transfers(self):
        from apps.tickets.tasks import expire_pending_transfers
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            status="pending",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        result = expire_pending_transfers()
        assert "Expired" in result
        transfer.refresh_from_db()
        assert transfer.status == TicketTransfer.Status.CANCELLED
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.ACTIVE

    def test_no_expired_transfers(self):
        from apps.tickets.tasks import expire_pending_transfers
        result = expire_pending_transfers()
        assert "0" in result

    def test_non_expired_not_cancelled(self):
        from apps.tickets.tasks import expire_pending_transfers
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            status="pending",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        expire_pending_transfers()
        transfer.refresh_from_db()
        assert transfer.status == TicketTransfer.Status.PENDING
