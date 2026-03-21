import pytest
from django.utils import timezone

from apps.companies.services import create_company
from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event
from apps.events.services import create_event, publish_event, unpublish_event, update_event

from .factories import EventFactory


@pytest.mark.django_db
class TestCreateEvent:
    def test_create_event(self):
        user = UserFactory()
        company = create_company(name="Test Co", owner=user)
        event = create_event(
            title="Test Event",
            description="Description",
            company=company,
            location="City",
            start_date=timezone.now() + timezone.timedelta(days=7),
            end_date=timezone.now() + timezone.timedelta(days=8),
            capacity=100,
            creator=user,
        )
        assert event.pk is not None
        assert event.status == Event.Status.DRAFT


@pytest.mark.django_db
class TestPublishUnpublishEvent:
    def test_publish_event(self):
        event = EventFactory(status="draft")
        result = publish_event(event)
        assert result.status == Event.Status.PUBLISHED

    def test_cannot_publish_cancelled(self):
        from rest_framework import serializers
        event = EventFactory(status="cancelled")
        with pytest.raises(serializers.ValidationError):
            publish_event(event)

    def test_unpublish_event(self):
        event = EventFactory(status="published")
        result = unpublish_event(event)
        assert result.status == Event.Status.DRAFT


@pytest.mark.django_db
class TestUploadCover:
    def test_upload_cover(self, tmp_path):
        from apps.events.services import upload_cover
        from django.core.files.uploadedfile import SimpleUploadedFile
        from io import BytesIO
        from PIL import Image

        user = UserFactory()
        company = create_company(name="Cover Co", owner=user)
        event = EventFactory(company=company)

        # Create a simple test image
        img = Image.new("RGB", (100, 100), color="red")
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        cover = SimpleUploadedFile("cover.png", img_io.read(), content_type="image/png")

        result = upload_cover(event=event, cover_image=cover, uploaded_by=user)
        assert result.cover_image
