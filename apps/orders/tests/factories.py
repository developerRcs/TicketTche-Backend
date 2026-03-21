import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.events.tests.factories import EventFactory, TicketTypeFactory
from apps.orders.models import Order, OrderItem


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    event = factory.SubFactory(EventFactory)
    buyer = factory.SubFactory(UserFactory)
    total = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    status = Order.Status.PENDING
    payment_status = Order.PaymentStatus.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(minutes=30))


class OrderItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    ticket_type = factory.SubFactory(TicketTypeFactory)
    quantity = 1
    unit_price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    subtotal = factory.LazyAttribute(lambda o: o.quantity * o.unit_price)
