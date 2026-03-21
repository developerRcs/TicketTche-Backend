import pytest

from apps.events.models import Event, TicketType

from .factories import EventFactory, TicketTypeFactory


@pytest.mark.django_db
class TestEvent:
    def test_event_creation(self):
        event = EventFactory()
        assert event.pk is not None
        assert event.status == Event.Status.DRAFT

    def test_slug_auto_generation(self):
        event = EventFactory(title="My Great Event")
        assert event.slug.startswith("my-great-event")

    def test_tickets_sold_property(self):
        event = EventFactory()
        TicketTypeFactory(event=event, quantity_sold=10)
        TicketTypeFactory(event=event, quantity_sold=5)
        assert event.tickets_sold == 15

    def test_str_representation(self):
        event = EventFactory(title="Test Event")
        assert str(event) == "Test Event"

    def test_uuid_primary_key(self):
        import uuid
        event = EventFactory()
        assert isinstance(event.pk, uuid.UUID)


@pytest.mark.django_db
class TestTicketType:
    def test_quantity_available_property(self):
        tt = TicketTypeFactory(quantity=100, quantity_sold=30)
        assert tt.quantity_available == 70

    def test_str_representation(self):
        tt = TicketTypeFactory()
        assert tt.event.title in str(tt)


@pytest.mark.django_db
class TestEventSlugCollision:
    def test_slug_uniqueness_suffix(self):
        """Force slug collision by manually setting slug."""
        from apps.events.models import Event
        from django.utils.text import slugify
        event1 = EventFactory(title="Collision Test Event")
        base_slug = slugify("Collision Test Event")
        # Override the slug to the base
        Event.objects.filter(pk=event1.pk).update(slug=base_slug)
        event1.refresh_from_db()
        # Now creating another with same title should get a different slug
        event2 = EventFactory(title="Collision Test Event")
        assert event2.slug != event1.slug

    def test_tickets_sold_no_types(self):
        event = EventFactory()
        assert event.tickets_sold == 0


@pytest.mark.django_db
class TestEventSlugCollisionLoop:
    """Covers the while loop body when first suffix also collides (lines 48-49)."""

    def test_slug_while_loop_iterates(self):
        from unittest.mock import patch, call
        from apps.events.models import Event
        from apps.companies.tests.factories import CompanyFactory

        company = CompanyFactory()
        call_count = [0]
        original_random = None

        import apps.events.models as events_models
        real_random = events_models.get_random_string

        def fake_random(length):
            call_count[0] += 1
            # First two calls return same suffix to force collision, then unique
            if call_count[0] <= 2:
                return "aaaaaa"
            return real_random(length)

        with patch("apps.events.models.get_random_string", side_effect=fake_random):
            e1 = Event(
                title="Loop Test", company=company,
                location="Here", start_date="2027-01-01T10:00:00Z",
                end_date="2027-01-01T18:00:00Z", capacity=100,
            )
            e1.save()
            e2 = Event(
                title="Loop Test", company=company,
                location="Here", start_date="2027-01-01T10:00:00Z",
                end_date="2027-01-01T18:00:00Z", capacity=100,
            )
            e2.save()

        assert e1.slug != e2.slug
        assert call_count[0] >= 3
