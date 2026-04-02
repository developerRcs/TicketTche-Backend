import pytest
from django.utils import timezone

from apps.events.filters import EventFilter
from apps.events.models import Event
from apps.events.tests.factories import EventFactory


@pytest.mark.django_db
class TestEventFilter:
    def test_filter_search_by_title(self):
        EventFactory(title="Unique Concert Event")
        EventFactory(title="Another Event")
        qs = Event.objects.all()
        f = EventFilter({"search": "Unique Concert"}, queryset=qs)
        assert f.qs.count() == 1

    def test_filter_search_by_description(self):
        EventFactory(description="Very special description here")
        EventFactory(description="Normal description")
        qs = Event.objects.all()
        f = EventFilter({"search": "Very special"}, queryset=qs)
        assert f.qs.count() == 1

    def test_filter_by_status(self):
        EventFactory(status="published")
        EventFactory(status="draft")
        qs = Event.objects.all()
        f = EventFilter({"status": "published"}, queryset=qs)
        assert all(e.status == "published" for e in f.qs)

    def test_filter_by_start_date_after(self):
        now = timezone.now()
        EventFactory(start_date=now + timezone.timedelta(days=10))
        EventFactory(start_date=now + timezone.timedelta(days=1))
        qs = Event.objects.all()
        cutoff = now + timezone.timedelta(days=5)
        f = EventFilter({"start_date_after": cutoff.isoformat()}, queryset=qs)
        assert f.qs.count() == 1

    def test_no_filter_returns_all(self):
        EventFactory.create_batch(3)
        qs = Event.objects.all()
        f = EventFilter({}, queryset=qs)
        assert f.qs.count() == 3
