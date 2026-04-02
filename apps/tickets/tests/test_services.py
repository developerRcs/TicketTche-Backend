import pytest
from rest_framework import serializers

from apps.accounts.tests.factories import UserFactory
from apps.tickets.models import Ticket, TicketTransfer
from apps.tickets.services import (
    accept_transfer,
    cancel_transfer,
    initiate_transfer,
    reject_transfer,
)

from .factories import TicketFactory, TicketTransferFactory


@pytest.mark.django_db
class TestInitiateTransfer:
    def test_initiate_transfer_success(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        to_user = UserFactory()
        transfer = initiate_transfer(str(ticket.pk), to_user.email, owner)
        assert transfer.status == TicketTransfer.Status.PENDING
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.PENDING_TRANSFER

    def test_initiate_transfer_wrong_owner(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner)
        other = UserFactory()
        with pytest.raises(serializers.ValidationError):
            initiate_transfer(str(ticket.pk), "someone@example.com", other)

    def test_initiate_transfer_non_active(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="used")
        with pytest.raises(serializers.ValidationError):
            initiate_transfer(str(ticket.pk), "someone@example.com", owner)

    def test_initiate_transfer_already_pending(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        TicketTransferFactory(ticket=ticket, from_user=owner, status="pending")
        ticket.status = "pending_transfer"
        ticket.save()
        with pytest.raises(serializers.ValidationError):
            initiate_transfer(str(ticket.pk), "other@example.com", owner)


@pytest.mark.django_db
class TestAcceptTransfer:
    def test_accept_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            to_email=to_user.email,
        )
        result = accept_transfer(transfer.pk, to_user)
        assert result.status == TicketTransfer.Status.ACCEPTED
        ticket.refresh_from_db()
        assert ticket.owner == to_user
        assert ticket.status == Ticket.Status.ACTIVE

    def test_accept_transfer_not_found(self):
        user = UserFactory()
        with pytest.raises(serializers.ValidationError):
            accept_transfer("00000000-0000-0000-0000-000000000000", user)


@pytest.mark.django_db
class TestRejectTransfer:
    def test_reject_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            to_email=to_user.email,
        )
        result = reject_transfer(transfer.pk, to_user)
        assert result.status == TicketTransfer.Status.REJECTED
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.ACTIVE


@pytest.mark.django_db
class TestCancelTransfer:
    def test_cancel_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            to_email=to_user.email,
        )
        result = cancel_transfer(transfer.pk, owner)
        assert result.status == TicketTransfer.Status.CANCELLED
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.ACTIVE


@pytest.mark.django_db
class TestGetTransfer:
    def test_get_transfer_exists(self):
        from apps.tickets.services import get_transfer
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        transfer = TicketTransferFactory(ticket=ticket, from_user=owner)
        result = get_transfer(transfer.pk)
        assert result == transfer

    def test_get_transfer_not_found(self):
        from apps.tickets.services import get_transfer
        import uuid
        with pytest.raises(TicketTransfer.DoesNotExist):
            get_transfer(uuid.uuid4())


@pytest.mark.django_db
class TestTransferToSelf:
    def test_cannot_transfer_to_self(self):
        owner = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        with pytest.raises(serializers.ValidationError):
            initiate_transfer(str(ticket.pk), owner.email, owner)


@pytest.mark.django_db
class TestAcceptTransferEdgeCases:
    def test_accept_non_pending_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket, from_user=owner, to_email=to_user.email, status="accepted"
        )
        with pytest.raises(serializers.ValidationError):
            accept_transfer(transfer.pk, to_user)

    def test_accept_expired_transfer(self):
        from django.utils import timezone
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="pending_transfer")
        transfer = TicketTransferFactory(
            ticket=ticket,
            from_user=owner,
            to_email=to_user.email,
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        with pytest.raises(serializers.ValidationError):
            accept_transfer(transfer.pk, to_user)


@pytest.mark.django_db
class TestRejectTransferEdgeCases:
    def test_reject_transfer_not_found(self):
        import uuid
        user = UserFactory()
        with pytest.raises(serializers.ValidationError):
            reject_transfer(uuid.uuid4(), user)

    def test_reject_non_pending_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        transfer = TicketTransferFactory(
            ticket=ticket, from_user=owner, to_email=to_user.email, status="rejected"
        )
        with pytest.raises(serializers.ValidationError):
            reject_transfer(transfer.pk, to_user)


@pytest.mark.django_db
class TestCancelTransferEdgeCases:
    def test_cancel_transfer_not_found(self):
        import uuid
        user = UserFactory()
        with pytest.raises(serializers.ValidationError):
            cancel_transfer(uuid.uuid4(), user)

    def test_cancel_non_pending_transfer(self):
        owner = UserFactory()
        to_user = UserFactory()
        ticket = TicketFactory(owner=owner, status="active")
        transfer = TicketTransferFactory(
            ticket=ticket, from_user=owner, to_email=to_user.email, status="cancelled"
        )
        with pytest.raises(serializers.ValidationError):
            cancel_transfer(transfer.pk, owner)


@pytest.mark.django_db
class TestCheckInTicket:
    def test_check_in_success(self):
        from apps.tickets.services import check_in_ticket
        from apps.companies.services import create_company
        staff = UserFactory()
        company = create_company(name="Test Co", owner=staff)
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="active")
        result = check_in_ticket(str(ticket.pk), staff)
        assert result.status == Ticket.Status.USED
        assert result.checked_in_at is not None

    def test_check_in_already_used(self):
        from apps.tickets.services import check_in_ticket
        from apps.companies.services import create_company
        staff = UserFactory()
        company = create_company(name="Test Co2", owner=staff)
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="used")
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(ticket.pk), staff)

    def test_check_in_cancelled_ticket(self):
        from apps.tickets.services import check_in_ticket
        from apps.companies.services import create_company
        staff = UserFactory()
        company = create_company(name="Test Co3", owner=staff)
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="cancelled")
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(ticket.pk), staff)

    def test_check_in_not_found(self):
        from apps.tickets.services import check_in_ticket
        import uuid
        staff = UserFactory()
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(uuid.uuid4()), staff)

    def test_check_in_unauthorized_staff(self):
        from apps.tickets.services import check_in_ticket
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        from apps.companies.tests.factories import CompanyFactory
        company = CompanyFactory()
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="active")
        non_staff = UserFactory()  # not a company member
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(ticket.pk), non_staff)

    def test_check_in_transferred_ticket(self):
        from apps.tickets.services import check_in_ticket
        from apps.companies.services import create_company
        staff = UserFactory()
        company = create_company(name="Test Co4", owner=staff)
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="transferred")
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(ticket.pk), staff)

    def test_check_in_pending_transfer(self):
        from apps.tickets.services import check_in_ticket
        from apps.companies.services import create_company
        staff = UserFactory()
        company = create_company(name="Test Co5", owner=staff)
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="pending_transfer")
        with pytest.raises(serializers.ValidationError):
            check_in_ticket(str(ticket.pk), staff)


@pytest.mark.django_db
class TestCheckInSuperAdmin:
    def test_check_in_as_super_admin(self):
        from apps.tickets.services import check_in_ticket
        from apps.accounts.tests.factories import SuperAdminFactory
        from apps.companies.tests.factories import CompanyFactory
        from apps.events.tests.factories import EventFactory, TicketTypeFactory
        super_admin = SuperAdminFactory()
        company = CompanyFactory()
        event = EventFactory(company=company)
        tt = TicketTypeFactory(event=event)
        ticket = TicketFactory(event=event, ticket_type=tt, status="active")
        result = check_in_ticket(str(ticket.pk), super_admin)
        assert result.status == Ticket.Status.USED
