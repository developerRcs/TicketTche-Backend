from apps.audit.services import log_action
from apps.companies.models import CompanyMember

from .models import Event, TicketType


def create_event(title, description, company, location, start_date, end_date, capacity, creator=None, request=None, **kwargs):
    event = Event.objects.create(
        title=title,
        description=description,
        company=company,
        location=location,
        start_date=start_date,
        end_date=end_date,
        capacity=capacity,
        **kwargs,
    )
    log_action(
        action="event_create",
        actor=creator,
        target=event,
        request=request,
    )
    return event


def update_event(event, updated_by=None, request=None, **kwargs):
    for attr, value in kwargs.items():
        setattr(event, attr, value)
    event.save()
    log_action(
        action="event_update",
        actor=updated_by,
        target=event,
        request=request,
    )
    return event


def publish_event(event, published_by=None, request=None):
    from rest_framework import serializers
    if event.status == Event.Status.CANCELLED:
        raise serializers.ValidationError({"status": "Cannot publish a cancelled event."})
    event.status = Event.Status.PUBLISHED
    event.save(update_fields=["status"])
    log_action(
        action="event_publish",
        actor=published_by,
        target=event,
        request=request,
    )
    return event


def unpublish_event(event, unpublished_by=None, request=None):
    event.status = Event.Status.DRAFT
    event.save(update_fields=["status"])
    log_action(
        action="event_unpublish",
        actor=unpublished_by,
        target=event,
        request=request,
    )
    return event


def upload_cover(event, cover_image, uploaded_by=None, request=None):
    event.cover_image = cover_image
    event.save(update_fields=["cover_image"])
    log_action(
        action="event_cover_upload",
        actor=uploaded_by,
        target=event,
        request=request,
    )
    return event
