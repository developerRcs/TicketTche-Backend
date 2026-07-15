from decimal import Decimal

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrSuperAdmin
from apps.companies.models import Company, CompanyMember
from apps.core.pagination import StandardPagination

from .models import Withdrawal
from .serializers import BalanceSerializer, WithdrawalCreateSerializer, WithdrawalSerializer
from .services import (
    approve_withdrawal,
    get_company_balance,
    reject_withdrawal,
    request_withdrawal,
    resolve_withdrawal,
)


def _get_company_or_403(company_id, user):
    """Return Company if user is an owner/admin member, else raise PermissionDenied."""
    from rest_framework.exceptions import NotFound, PermissionDenied

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        raise NotFound("Empresa não encontrada.")

    is_member = CompanyMember.objects.filter(
        user=user,
        company=company,
        role__in=[CompanyMember.Role.OWNER, CompanyMember.Role.ADMIN],
    ).exists()

    if not is_member:
        raise PermissionDenied("Você não tem permissão para acessar os saques desta empresa.")

    return company


class CompanyBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, company_id):
        _get_company_or_403(company_id, request.user)
        balance = get_company_balance(str(company_id))
        serializer = BalanceSerializer(balance)
        return Response(serializer.data)


from apps.core.throttling import WithdrawalRateThrottle


class WithdrawalListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [WithdrawalRateThrottle]

    def get(self, request, company_id):
        company = _get_company_or_403(company_id, request.user)
        qs = Withdrawal.objects.filter(company=company).select_related(
            "company", "requested_by"
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = WithdrawalSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, company_id):
        company = _get_company_or_403(company_id, request.user)
        serializer = WithdrawalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        withdrawal = request_withdrawal(
            company=company,
            user=request.user,
            amount=Decimal(str(data["amount"])),
            pix_key=data["pix_key"],
            pix_key_type=data["pix_key_type"],
        )

        return Response(
            WithdrawalSerializer(withdrawal).data,
            status=status.HTTP_201_CREATED,
        )


class AdminWithdrawalListView(generics.ListAPIView):
    """Platform-admin queue of withdrawals (filter by ?status=pending etc.)."""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]
    serializer_class = WithdrawalSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Withdrawal.objects.select_related("company", "requested_by").order_by("created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminWithdrawalApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]

    def post(self, request, withdrawal_id):
        withdrawal = approve_withdrawal(str(withdrawal_id), request.user)
        return Response(WithdrawalSerializer(withdrawal).data)


class AdminWithdrawalRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]

    def post(self, request, withdrawal_id):
        reason = str(request.data.get("reason", ""))[:500]
        withdrawal = reject_withdrawal(str(withdrawal_id), request.user, reason)
        return Response(WithdrawalSerializer(withdrawal).data)


class AdminWithdrawalResolveView(APIView):
    """Manually close a PROCESSING withdrawal (MANUAL- transfers or stuck polls)."""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]

    def post(self, request, withdrawal_id):
        final_status = str(request.data.get("status", ""))
        reason = str(request.data.get("reason", ""))[:500]
        withdrawal = resolve_withdrawal(str(withdrawal_id), request.user, final_status, reason)
        return Response(WithdrawalSerializer(withdrawal).data)
