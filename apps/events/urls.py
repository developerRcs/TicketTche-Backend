from django.urls import path

from .views import (
    EventCoverView,
    EventCreateView,
    EventDetailView,
    EventListView,
    MyEventsView,
    PublishEventView,
    UnpublishEventView,
)

urlpatterns = [
    path("", EventListView.as_view(), name="event_list"),
    path("create/", EventCreateView.as_view(), name="event_create"),
    path("my/", MyEventsView.as_view(), name="my_events"),
    path("<uuid:pk>/", EventDetailView.as_view(), name="event_detail"),
    path("<uuid:pk>/publish/", PublishEventView.as_view(), name="event_publish"),
    path("<uuid:pk>/unpublish/", UnpublishEventView.as_view(), name="event_unpublish"),
    path("<uuid:pk>/cover/", EventCoverView.as_view(), name="event_cover"),
]
