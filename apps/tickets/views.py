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
        import hashlib
        import hmac as hmac_module
        from django.conf import settings
        from rest_framework.exceptions import ValidationError as DRFValidationError

        code = request.data.get("code", "").strip()
        parts = code.split(":")
        if len(parts) != 2:
            return Response({"valid": False, "error": "QR code inválido."}, status=status.HTTP_400_BAD_REQUEST)

        ticket_id, received_sig = parts
        signing_key = settings.QR_SIGNING_KEY.encode()
        expected_sig = hmac_module.new(
            signing_key, ticket_id.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac_module.compare_digest(expected_sig, received_sig):
            return Response({"valid": False, "error": "QR code adulterado ou inválido."}, status=status.HTTP_400_BAD_REQUEST)

        from .services import check_in_ticket

        def ticket_info(ticket, valid, error=None):
            raw_cpf = getattr(ticket.owner, "cpf", "") or ""
            raw_cpf = raw_cpf.strip()
            if len(raw_cpf) == 14:  # "000.000.000-00"
                masked_cpf = f"***.{raw_cpf[4:7]}.{raw_cpf[8:11]}-**"
            elif len(raw_cpf) == 11:  # "00000000000" raw digits
                masked_cpf = f"***.{raw_cpf[3:6]}.{raw_cpf[6:9]}-**"
            else:
                masked_cpf = "***"

            data = {
                "valid": valid,
                "id": str(ticket.id),
                "event_title": ticket.event.title,
                "ticket_type": ticket.ticket_type.name,
                "holder_name": ticket.owner.full_name,
                "holder_email": ticket.owner.email,
                "holder_cpf": masked_cpf,
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

class TransferInviteView(APIView):
    """Resolve opaque invite token → return transfer context for frontend."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        import json
        from django.core.cache import cache

        raw = cache.get(f"ticket:transfer:invite:{token}")
        if not raw:
            return Response(
                {"detail": "Convite inválido ou expirado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = json.loads(raw)
        transfer_id = data.get("transfer_id")

        try:
            transfer = TicketTransfer.objects.select_related(
                "ticket__event", "from_user"
            ).get(id=transfer_id)
        except TicketTransfer.DoesNotExist:
            return Response(
                {"detail": "Transferência não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "to_email": transfer.to_email,
            "event_title": transfer.ticket.event.title,
            "sender_name": transfer.from_user.first_name or transfer.from_user.email,
            "transfer_id": str(transfer.id),
            "status": transfer.status,
        })