from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import Ticket, TicketTransfer
from .permissions import IsTicketOwner
from .serializers import InitiateTransferSerializer, TicketSerializer, TicketTransferSerializer
from .services import (
    accept_transfer,
    cancel_transfer,
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
