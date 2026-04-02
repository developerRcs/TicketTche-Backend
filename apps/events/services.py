import urllib.parse
import urllib.request
import json
import logging

from apps.audit.services import log_action
from apps.companies.models import CompanyMember

from .models import Event, TicketType

logger = logging.getLogger(__name__)


def geocode_location(location: str) -> tuple[float, float] | tuple[None, None]:
    """Geocode a location string using Nominatim (OpenStreetMap). Returns (lat, lng) or (None, None)."""
    try:
        query = urllib.parse.urlencode({"q": location, "format": "json", "limit": 1})
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "TicketTche/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning("Geocoding failed for '%s': %s", location, e)
    return None, None


def create_event(title, description, company, location, start_date, end_date, capacity, creator=None, request=None, **kwargs):
    lat, lng = geocode_location(location)
    event = Event.objects.create(
        title=title,
        description=description,
        company=company,
        location=location,
        start_date=start_date,
        end_date=end_date,
        capacity=capacity,
        latitude=lat,
        longitude=lng,
        **kwargs,
    )
    log_action(
        action="event_create",
        actor=creator,
        target=event,
        request=request,
    )
    return event


def sync_ticket_types(event, ticket_types_data: list):
    """
    Syncs ticket types for an event based on submitted data.
    - Items with an 'id' → update existing
    - Items without 'id' → create new
    - Existing types not in the submitted list → delete (if no sold tickets)
    """
    submitted_ids = {str(tt["id"]) for tt in ticket_types_data if tt.get("id")}

    # Delete removed types that have no sold tickets
    for tt in TicketType.objects.filter(event=event).exclude(id__in=submitted_ids):
        if tt.quantity_sold == 0:
            tt.delete()

    for tt_data in ticket_types_data:
        tt_data = dict(tt_data)
        tt_id = tt_data.pop("id", None)

        if tt_id:
            TicketType.objects.filter(id=tt_id, event=event).update(**tt_data)
        else:
            TicketType.objects.create(event=event, **tt_data)


def update_event(event, updated_by=None, request=None, **kwargs):
    if "location" in kwargs and kwargs["location"] != event.location:
        lat, lng = geocode_location(kwargs["location"])
        kwargs.setdefault("latitude", lat)
        kwargs.setdefault("longitude", lng)
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
