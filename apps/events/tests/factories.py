import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.companies.tests.factories import CompanyFactory
from apps.events.models import Event, TicketType


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    title = factory.Sequence(lambda n: f"Event {n}")
    description = factory.Faker("text")
    company = factory.SubFactory(CompanyFactory)
    location = factory.Faker("city")
    start_date = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=7))
    end_date = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=8))
    status = Event.Status.DRAFT
    capacity = 100
    is_online = False


class TicketTypeFactory(DjangoModelFactory):
    class Meta:
        model = TicketType

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Ticket Type {n}")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    quantity = 50
    quantity_sold = 0
