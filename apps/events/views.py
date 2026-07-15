from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOrganizerOrAdmin
from apps.companies.models import CompanyMember
from apps.core.pagination import StandardPagination

from .filters import EventFilter
from .models import Event
from .permissions import IsEventOrganizer
from .serializers import EventCoverSerializer, EventCreateSerializer, EventSerializer, EventUpdateSerializer
from .services import create_event, publish_event, sync_ticket_types, unpublish_event, update_event, upload_cover


class EventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    pagination_class = StandardPagination
    filterset_class = EventFilter
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    ordering_fields = ["start_date", "created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        from django.db.models import Q

        qs = Event.objects.select_related("company").prefetch_related("ticket_types").order_by("-created_at")
        user = self.request.user
        if not user.is_authenticated:
            return qs.filter(status=Event.Status.PUBLISHED)
        if getattr(user, "role", "") in ("admin", "super_admin"):
            return qs
        # Drafts/cancelled events are only visible to members of the owning company
        member_companies = CompanyMember.objects.filter(user=user).values_list("company_id", flat=True)
        return qs.filter(Q(status=Event.Status.PUBLISHED) | Q(company__in=member_companies))


class EventCreateView(generics.CreateAPIView):
    serializer_class = EventCreateSerializer
    permission_classes = [IsOrganizerOrAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Events can only be created under a company the user manages
        is_platform_admin = getattr(request.user, "role", "") in ("admin", "super_admin")
        if not is_platform_admin and not CompanyMember.objects.filter(
            user=request.user,
            company=data["company"],
            role__in=[CompanyMember.Role.OWNER, CompanyMember.Role.ADMIN],
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Você não tem permissão para criar eventos nesta empresa.")

        ticket_types_data = data.pop("ticket_types", [])
        event = create_event(
            creator=request.user,
            request=request,
            **data,
        )
        from .models import TicketType
        for tt_data in ticket_types_data:
            TicketType.objects.create(event=event, **tt_data)
        output = EventSerializer(event)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MyEventsView(generics.ListAPIView):
    serializer_class = EventSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_companies = CompanyMember.objects.filter(user=self.request.user).values_list(
            "company_id", flat=True
        )
        return Event.objects.filter(company__in=user_companies).select_related(
            "company"
        ).prefetch_related("ticket_types").order_by("-created_at")


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.select_related("company").prefetch_related("ticket_types")

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return EventUpdateSerializer
        return EventSerializer

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [permissions.IsAuthenticated(), IsEventOrganizer()]
        return [permissions.AllowAny()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != Event.Status.PUBLISHED:
            user = request.user
            is_member = (
                user.is_authenticated
                and (
                    getattr(user, "role", "") in ("admin", "super_admin")
                    or CompanyMember.objects.filter(user=user, company=instance.company).exists()
                )
            )
            if not is_member:
                from rest_framework.exceptions import NotFound
                raise NotFound()
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        from apps.tickets.models import Ticket

        if Ticket.objects.filter(event=instance).exists():
            return Response(
                {
                    "detail": (
                        "Este evento possui ingressos vendidos e não pode ser excluído. "
                        "Cancele o evento em vez de excluí-lo."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        ticket_types_data = serializer.validated_data.pop("ticket_types", None)
        updated = update_event(instance, updated_by=request.user, request=request, **serializer.validated_data)
        if ticket_types_data is not None:
            sync_ticket_types(updated, ticket_types_data)
        updated.refresh_from_db()
        return Response(EventSerializer(updated).data)


class PublishEventView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)
        event = publish_event(event, published_by=request.user, request=request)
        return Response(EventSerializer(event).data)


class UnpublishEventView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)
        event = unpublish_event(event, unpublished_by=request.user, request=request)
        return Response(EventSerializer(event).data)


class EventCoverView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]
    parser_classes = [MultiPartParser]

    def patch(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        self.check_object_permissions(request, event)
        serializer = EventCoverSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        event = upload_cover(
            event=event,
            cover_image=serializer.validated_data["cover_image"],
            uploaded_by=request.user,
            request=request,
        )
        return Response(EventSerializer(event).data)


class OrganizerStatsView(APIView):
    permission_classes = [IsOrganizerOrAdmin]

    def get(self, request):
        from django.db.models import Sum, Count, Avg
        from apps.orders.models import Order
        from apps.tickets.models import Ticket

        user_companies = CompanyMember.objects.filter(user=request.user).values_list("company_id", flat=True)
        events = Event.objects.filter(company__in=user_companies)

        total_events = events.count()
        published_events = events.filter(status=Event.Status.PUBLISHED).count()

        paid_orders = Order.objects.filter(
            event__in=events, status=Order.Status.PAID
        )
        revenue_data = paid_orders.aggregate(
            total_revenue=Sum("grand_total"),
            total_tickets=Sum("items__quantity"),
        )
        total_revenue = revenue_data["total_revenue"] or 0
        total_tickets = revenue_data["total_tickets"] or 0
        avg_ticket = (total_revenue / total_tickets) if total_tickets else 0

        recent_events = events.order_by("-created_at")[:5]

        return Response({
            "total_events": total_events,
            "published_events": published_events,
            "total_tickets_sold": total_tickets,
            "total_revenue": str(round(total_revenue, 2)),
            "avg_ticket_price": str(round(float(avg_ticket), 2)),
            "recent_events": EventSerializer(recent_events, many=True).data,
        })
