from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import Ticket, TicketTransfer
from .permissions import IsTicketOwner
from .serializers import (
    ConfirmTransferByOwnerSerializer,
    InitiateTransferSerializer,
    TicketSerializer,
    TicketTransferSerializer,
)
from .services import (
    accept_transfer,
    cancel_transfer,
    confirm_transfer_by_owner,
    confirm_transfer_payment,
    get_user_tickets,
    initiate_transfer,
    reject_transfer,
)


class MyTicketsView(generics.ListAPIView):
    serializer_class = TicketSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return get_user_tickets(self.request.user, status=status_filter)


class TicketDetailView(generics.RetrieveAPIView):
    serializer_class = TicketSerializer

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user)


class InitiateTransferView(APIView):
    def post(self, request):
        serializer = InitiateTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = initiate_transfer(
            ticket_id=serializer.validated_data["ticket_id"],
            to_email=serializer.validated_data["to_email"],
            agreed_price=serializer.validated_data.get("agreed_price"),
            from_user=request.user,
            request=request,
        )
        return Response(TicketTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


class AcceptTransferView(APIView):
    def post(self, request, pk):
        transfer = accept_transfer(transfer_id=pk, accepting_user=request.user, request=request)
        return Response(TicketTransferSerializer(transfer).data)


class RejectTransferView(APIView):
    def post(self, request, pk):
        transfer = reject_transfer(transfer_id=pk, rejecting_user=request.user, request=request)
        return Response(TicketTransferSerializer(transfer).data)


class CancelTransferView(APIView):
    def post(self, request, pk):
        transfer = cancel_transfer(transfer_id=pk, cancelling_user=request.user, request=request)
        return Response(TicketTransferSerializer(transfer).data)


class PendingTransfersView(generics.ListAPIView):
    serializer_class = TicketTransferSerializer

    def get_queryset(self):
        return TicketTransfer.objects.filter(
            to_email=self.request.user.email,
            status=TicketTransfer.Status.PENDING,
        ).select_related("ticket", "from_user")


class ConfirmTransferByOwnerView(APIView):
    def post(self, request, pk):
        serializer = ConfirmTransferByOwnerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = confirm_transfer_by_owner(
            transfer_id=pk,
            confirmation_code=serializer.validated_data["confirmation_code"],
            owner_user=request.user,
            request=request,
        )
        return Response(TicketTransferSerializer(transfer).data)


class ConfirmTransferPaymentView(APIView):
    def post(self, request, pk):
        transfer = confirm_transfer_payment(
            transfer_id=pk,
            accepting_user=request.user,
            request=request,
        )
        return Response(TicketTransferSerializer(transfer).data)


class TicketCheckInView(APIView):
    """
    POST /api/v1/tickets/check-in/
    Body: { "code": "<ticket_uuid>:<secret8>" }
    Validates the QR code, marks the ticket as used, and returns holder info.
    Only organizers/staff of the event company (or admins) can use this.
    """

    def post(self, request):
        from django.conf import settings
        from rest_framework.exceptions import ValidationError as DRFValidationError

        code = request.data.get("code", "").strip()
        parts = code.split(":")
        if len(parts) != 2:
            return Response({"valid": False, "error": "QR code inválido."}, status=status.HTTP_400_BAD_REQUEST)

        ticket_id, secret = parts
        if secret != settings.SECRET_KEY[:8]:
            return Response({"valid": False, "error": "QR code adulterado ou inválido."}, status=status.HTTP_400_BAD_REQUEST)

        from .services import check_in_ticket

        def ticket_info(ticket, valid, error=None):
            data = {
                "valid": valid,
                "id": str(ticket.id),
                "event_title": ticket.event.title,
                "ticket_type": ticket.ticket_type.name,
                "holder_name": ticket.owner.full_name,
                "holder_email": ticket.owner.email,
                "status": ticket.status,
                "checked_in_at": ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
            }
            if error:
                data["error"] = error
            return data

        try:
            ticket = check_in_ticket(ticket_id, request.user, request)
            return Response(ticket_info(ticket, valid=True))
        except DRFValidationError as exc:
            detail = exc.detail
            # Try to load ticket info even on failure (e.g. already used)
            try:
                ticket = Ticket.objects.select_related("event", "owner", "ticket_type").get(pk=ticket_id)
                # Extract human-readable message from detail dict/list
                if isinstance(detail, dict):
                    msg = " ".join(str(v[0]) if isinstance(v, list) else str(v) for v in detail.values())
                else:
                    msg = str(detail)
                return Response(ticket_info(ticket, valid=False, error=msg), status=status.HTTP_400_BAD_REQUEST)
            except Ticket.DoesNotExist:
                return Response({"valid": False, "error": "Ingresso não encontrado."}, status=status.HTTP_404_NOT_FOUND)
