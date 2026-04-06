from django.conf import settings
from django.urls import path

from .views import (
    AcceptTransferView,
    CancelTransferView,
    ConfirmTransferByOwnerView,
    ConfirmTransferPaymentView,
    InitiateTransferView,
    MyTicketsView,
    PendingTransfersView,
    RejectTransferView,
    TicketCheckInView,
    TicketDetailView,
    TransferInviteView,
)

urlpatterns = [
    path("my/", MyTicketsView.as_view(), name="my_tickets"),
    path("check-in/", TicketCheckInView.as_view(), name="ticket_check_in"),
    path("<uuid:pk>/", TicketDetailView.as_view(), name="ticket_detail"),
    path("transfers/", InitiateTransferView.as_view(), name="initiate_transfer"),
    path("transfers/pending/", PendingTransfersView.as_view(), name="pending_transfers"),
    path("transfers/<uuid:pk>/accept/", AcceptTransferView.as_view(), name="accept_transfer"),
    path("transfers/<uuid:pk>/reject/", RejectTransferView.as_view(), name="reject_transfer"),
    path("transfers/<uuid:pk>/cancel/", CancelTransferView.as_view(), name="cancel_transfer"),
    path("transfers/<uuid:pk>/confirm-owner/", ConfirmTransferByOwnerView.as_view(), name="confirm_transfer_owner"),
    path("transfers/<uuid:pk>/confirm-payment/", ConfirmTransferPaymentView.as_view(), name="confirm_transfer_payment"),
    path("transfer-invite/<str:token>/", TransferInviteView.as_view(), name="transfer_invite"),
]

if settings.DEBUG:
    from .debug_views import (
        DebugCreateInviteTokenView,
        DebugCreateTicketView,
        DebugRegisterView,
        DebugTokenView,
        DebugTransferCodeView,
    )

    urlpatterns += [
        path("debug/register/", DebugRegisterView.as_view(), name="debug_register"),
        path("debug/token/", DebugTokenView.as_view(), name="debug_token"),
        path("debug/create-ticket/", DebugCreateTicketView.as_view(), name="debug_create_ticket"),
        path("debug/transfer/<uuid:pk>/code/", DebugTransferCodeView.as_view(), name="debug_transfer_code"),
        path("debug/transfer/<uuid:pk>/invite-token/", DebugCreateInviteTokenView.as_view(), name="debug_invite_token"),
    ]
