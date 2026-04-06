"""
DEBUG-ONLY views for E2E testing. These are NEVER accessible in production
because they are only registered when settings.DEBUG is True.
"""
import json
import random
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket, TicketTransfer


def _generate_valid_cpf() -> str:
    """Generate a random but mathematically valid CPF in format ###.###.###-##."""
    while True:
        digits = [random.randint(0, 9) for _ in range(9)]
        # Reject all-same sequences
        if len(set(digits)) == 1:
            continue
        total = sum(digits[i] * (10 - i) for i in range(9))
        r = (total * 10) % 11
        d1 = 0 if r == 10 else r
        digits.append(d1)
        total = sum(digits[i] * (11 - i) for i in range(10))
        r = (total * 10) % 11
        d2 = 0 if r == 10 else r
        digits.append(d2)
        s = "".join(map(str, digits))
        return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


class DebugTokenView(APIView):
    """
    POST /api/v1/tickets/debug/token/
    Returns a JWT access token for the given email, bypassing rate-limiting.
    Body: {email}
    Returns: {access}
    DEBUG ONLY.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        email = request.data.get("email")
        if not email:
            return Response({"detail": "email required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        token = AccessToken.for_user(user)
        return Response({"access": str(token)})


class DebugRegisterView(APIView):
    """
    POST /api/v1/tickets/debug/register/
    Creates a fresh user with auto-generated unique CPF.
    Body: {email, first_name?, last_name?}
    Returns: {email, password, user_id}
    DEBUG ONLY.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        User = get_user_model()
        email = request.data.get("email")
        if not email:
            return Response({"detail": "email required"}, status=status.HTTP_400_BAD_REQUEST)

        # Delete existing user with same email (idempotent for tests)
        User.objects.filter(email=email).delete()

        # Generate a unique valid CPF
        for _ in range(50):
            cpf = _generate_valid_cpf()
            if not User.objects.filter(cpf=cpf).exists():
                break

        password = "Testpass123!"
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=request.data.get("first_name", "Test"),
            last_name=request.data.get("last_name", "User"),
            cpf=cpf,
        )
        return Response(
            {"email": email, "password": password, "user_id": str(user.id)},
            status=status.HTTP_201_CREATED,
        )


class DebugCreateTicketView(APIView):
    """
    POST /api/v1/tickets/debug/create-ticket/
    Creates an event, ticket type, and active ticket for the authenticated user.
    Also adds the user as a CompanyMember so they can perform check-in.
    Returns: {ticket_id, event_id, event_title, ticket_type_id, check_in_code}
    DEBUG ONLY.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        from apps.events.models import Event, TicketType
        from apps.companies.models import Company, CompanyMember

        # Reuse or create a stable test company
        company, _ = Company.objects.get_or_create(
            name="__e2e_test_company__",
            defaults={
                "owner": request.user,
                "description": "Auto-created for E2E tests",
                "is_active": True,
            },
        )

        # Add user as CompanyMember so they can perform check-in
        CompanyMember.objects.get_or_create(
            company=company,
            user=request.user,
            defaults={"role": "admin"},
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

        # Build the check-in QR code content: "{ticket_uuid}:{SECRET_KEY[:8]}"
        check_in_code = f"{ticket.id}:{settings.SECRET_KEY[:8]}"

        return Response(
            {
                "ticket_id": str(ticket.id),
                "event_id": str(event.id),
                "event_title": event.title,
                "ticket_type_id": str(ticket_type.id),
                "check_in_code": check_in_code,
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
