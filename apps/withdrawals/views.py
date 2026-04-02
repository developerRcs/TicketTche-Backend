from decimal import Decimal

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company, CompanyMember
from apps.core.pagination import StandardPagination

from .models import Withdrawal
from .serializers import BalanceSerializer, WithdrawalCreateSerializer, WithdrawalSerializer
from .services import get_company_balance, request_withdrawal


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


class WithdrawalListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
