import pytest
from django.utils import timezone

from apps.tickets.models import Ticket, TicketTransfer

from .factories import TicketFactory, TicketTransferFactory


@pytest.mark.django_db
class TestTicket:
    def test_ticket_creation(self):
        ticket = TicketFactory()
        assert ticket.pk is not None
        assert ticket.status == Ticket.Status.ACTIVE

    def test_qr_code_generation(self):
        ticket = TicketFactory()
        # QR code should be generated on first save
        ticket.refresh_from_db()
        assert ticket.qr_code

    def test_str_representation(self):
        ticket = TicketFactory()
        assert str(ticket.id)[:8] in str(ticket)

    def test_uuid_primary_key(self):
        import uuid
        ticket = TicketFactory()
        assert isinstance(ticket.pk, uuid.UUID)


@pytest.mark.django_db
class TestTicketTransfer:
    def test_transfer_creation(self):
        transfer = TicketTransferFactory()
        assert transfer.pk is not None
        assert transfer.status == TicketTransfer.Status.PENDING

    def test_token_auto_generation(self):
        transfer = TicketTransferFactory()
        assert transfer.token
        assert len(transfer.token) == 64

    def test_expires_at_default(self):
        transfer = TicketTransferFactory()
        assert transfer.expires_at > timezone.now()

    def test_str_representation(self):
        transfer = TicketTransferFactory()
        assert transfer.from_user.email in str(transfer)
