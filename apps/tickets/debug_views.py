"""
DEBUG-ONLY views for E2E testing. These are NEVER accessible in production
because they are only registered when settings.DEBUG is True.
"""
import json
import secrets

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket, TicketTransfer


class DebugCreateTicketView(APIView):
    """
    POST /api/v1/tickets/debug/create-ticket/
    Creates an event, ticket type, and active ticket for the authenticated user.
    Returns: {ticket_id, event_id, event_title, ticket_type_id}
    DEBUG ONLY.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        from apps.events.models import Event, TicketType
        from apps.companies.models import Company

        # Reuse or create a stable test company
        company, _ = Company.objects.get_or_create(
            name="__e2e_test_company__",
            defaults={
                "owner": request.user,
                "description": "Auto-created for E2E tests",
                "is_active": True,
            },
        )

        # Create a unique event each time
        event = Event.objects.create(
            title="E2E Test Event",
            description="Evento criado automaticamente para testes E2E.",
            company=company,
            location="Sala de Testes, Porto Alegre",
            city="Porto Alegre",
            start_date=timezone.now() + timedelta(days=7),
            end_date=timezone.now() + timedelta(days=8),
            status=Event.Status.PUBLISHED,
            capacity=100,
        )

        ticket_type = TicketType.objects.create(
            event=event,
            name="Inteira",
            price="50.00",
            quantity=50,
        )

        ticket = Ticket.objects.create(
            event=event,
            ticket_type=ticket_type,
            owner=request.user,
            status=Ticket.Status.ACTIVE,
        )

        return Response(
            {
                "ticket_id": str(ticket.id),
                "event_id": str(event.id),
                "event_title": event.title,
                "ticket_type_id": str(ticket_type.id),
            },
            status=status.HTTP_201_CREATED,
        )


class DebugTransferCodeView(APIView):
    """
    GET /api/v1/tickets/debug/transfer/<pk>/code/
    Returns the confirmation code for a pending transfer owned by the authenticated user.
    DEBUG ONLY.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            transfer = TicketTransfer.objects.get(id=pk, from_user=request.user)
        except TicketTransfer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"confirmation_code": transfer.confirmation_code})


class DebugCreateInviteTokenView(APIView):
    """
    POST /api/v1/tickets/debug/transfer/<pk>/invite-token/
    Creates a fresh Redis invite token for the given transfer.
    Returns: {invite_token}
    DEBUG ONLY.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            transfer = TicketTransfer.objects.get(id=pk, from_user=request.user)
        except TicketTransfer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        invite_token = secrets.token_urlsafe(32)
        cache.set(
            f"ticket:transfer:invite:{invite_token}",
            json.dumps({"transfer_id": str(transfer.id), "to_email": transfer.to_email}),
            timeout=48 * 3600,
        )
        return Response({"invite_token": invite_token})
