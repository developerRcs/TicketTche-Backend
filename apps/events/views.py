from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import CompanyMember
from apps.core.pagination import StandardPagination

from .filters import EventFilter
from .models import Event
from .permissions import IsEventOrganizer
from .serializers import EventCoverSerializer, EventCreateSerializer, EventSerializer
from .services import create_event, publish_event, unpublish_event, update_event, upload_cover


class EventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    pagination_class = StandardPagination
    filterset_class = EventFilter
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ["start_date", "created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Event.objects.select_related("company").prefetch_related("ticket_types").order_by("-created_at")


class EventCreateView(generics.CreateAPIView):
    serializer_class = EventCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
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
            return EventCreateSerializer
        return EventSerializer

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [permissions.IsAuthenticated(), IsEventOrganizer()]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("ticket_types", None)
        updated = update_event(instance, updated_by=request.user, request=request, **data)
        return Response(EventSerializer(updated).data)


class PublishEventView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]

    def post(self, request, pk):
        event = Event.objects.get(pk=pk)
        self.check_object_permissions(request, event)
        event = publish_event(event, published_by=request.user, request=request)
        return Response(EventSerializer(event).data)


class UnpublishEventView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]

    def post(self, request, pk):
        event = Event.objects.get(pk=pk)
        self.check_object_permissions(request, event)
        event = unpublish_event(event, unpublished_by=request.user, request=request)
        return Response(EventSerializer(event).data)


class EventCoverView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEventOrganizer]
    parser_classes = [MultiPartParser]

    def patch(self, request, pk):
        event = Event.objects.get(pk=pk)
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
