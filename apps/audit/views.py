from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum

from apps.accounts.models import CustomUser
from apps.accounts.permissions import IsAdminOrSuperAdmin
from apps.accounts.serializers import AdminUserSerializer
from apps.companies.models import Company
from apps.companies.serializers import CompanySerializer
from apps.core.pagination import StandardPagination
from apps.events.models import Event
from apps.events.serializers import EventSerializer
from apps.orders.models import Order

from .models import AuditLog
from .serializers import AuditLogSerializer


class AdminStatsView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def get(self, request):
        from apps.orders.serializers import OrderSerializer
        total_revenue = Order.objects.filter(status="paid").aggregate(
            total=Sum("total")
        )["total"] or 0
        recent_orders = Order.objects.order_by("-created_at")[:5]
        order_serializer = OrderSerializer(recent_orders, many=True)

        stats = {
            "total_companies": Company.objects.count(),
            "total_events": Event.objects.count(),
            "total_users": CustomUser.objects.count(),
            "total_orders": Order.objects.count(),
            "total_revenue": str(total_revenue),
            "active_events": Event.objects.filter(status="published").count(),
            "recent_orders": order_serializer.data,
        }
        return Response(stats)


class AdminUsersListView(generics.ListAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]

    def get_queryset(self):
        qs = CustomUser.objects.all().order_by("-date_joined")
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs


class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    queryset = CustomUser.objects.all()


class AdminUserActivateView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        user.is_active = True
        user.save()
        return Response(AdminUserSerializer(user).data)


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]

    def post(self, request, pk):
        user = CustomUser.objects.get(pk=pk)
        user.is_active = False
        user.save()
        return Response(AdminUserSerializer(user).data)


class AdminCompaniesListView(generics.ListAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAdminOrSuperAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Company.objects.all().order_by("-created_at")
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class AdminEventsListView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Event.objects.all().order_by("-created_at")
        search = self.request.query_params.get("search")
        status = self.request.query_params.get("status")
        if search:
            qs = qs.filter(title__icontains=search)
        if status:
            qs = qs.filter(status=status)
        return qs


class AdminAuditLogView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminOrSuperAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor").order_by("-created_at")
        action = self.request.query_params.get("action")
        actor = self.request.query_params.get("actor")
        if action:
            qs = qs.filter(action=action)
        if actor:
            qs = qs.filter(actor__email__icontains=actor)
        return qs
