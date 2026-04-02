import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.tickets.models import Ticket, TicketTransfer


class TicketFactory(DjangoModelFactory):
    class Meta:
        model = Ticket
        skip_postgeneration_save = True

    event = factory.SubFactory(EventFactory)
    ticket_type = factory.SubFactory(TicketTypeFactory)
    owner = factory.SubFactory(UserFactory)
    status = Ticket.Status.ACTIVE


class TicketTransferFactory(DjangoModelFactory):
    class Meta:
        model = TicketTransfer

    ticket = factory.SubFactory(TicketFactory)
    from_user = factory.SubFactory(UserFactory)
    to_email = factory.Faker("email")
    status = TicketTransfer.Status.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(hours=48))
