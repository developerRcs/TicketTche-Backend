from django.urls import path

from .views import (
    AcceptTransferView,
    CancelTransferView,
    InitiateTransferView,
    MyTicketsView,
    PendingTransfersView,
    RejectTransferView,
    TicketDetailView,
)

urlpatterns = [
    path("my/", MyTicketsView.as_view(), name="my_tickets"),
    path("<uuid:pk>/", TicketDetailView.as_view(), name="ticket_detail"),
    path("transfers/", InitiateTransferView.as_view(), name="initiate_transfer"),
    path("transfers/pending/", PendingTransfersView.as_view(), name="pending_transfers"),
    path("transfers/<uuid:pk>/accept/", AcceptTransferView.as_view(), name="accept_transfer"),
    path("transfers/<uuid:pk>/reject/", RejectTransferView.as_view(), name="reject_transfer"),
    path("transfers/<uuid:pk>/cancel/", CancelTransferView.as_view(), name="cancel_transfer"),
]
