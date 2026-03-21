from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from .models import Company, CompanyMember
from .permissions import IsCompanyOwnerOrAdmin
from .serializers import (
    CompanyCreateSerializer,
    CompanyMemberSerializer,
    CompanySerializer,
    InviteMemberSerializer,
    UpdateMemberRoleSerializer,
)
from .services import create_company, invite_member, remove_member, update_member_role


class CompanyListCreateView(generics.ListCreateAPIView):
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CompanyCreateSerializer
        return CompanySerializer

    def get_queryset(self):
        return Company.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        data = serializer.validated_data
        company = create_company(
            name=data["name"],
            owner=self.request.user,
            description=data.get("description", ""),
            logo=data.get("logo"),
            request=self.request,
        )
        self._created_company = company

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = CompanySerializer(self._created_company)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MyCompaniesView(generics.ListAPIView):
    serializer_class = CompanySerializer

    def get_queryset(self):
        return Company.objects.filter(
            members__user=self.request.user
        ).distinct().order_by("-created_at")


class CompanyDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT"]:
            return [permissions.IsAuthenticated(), IsCompanyOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]


class CompanyMembersView(generics.ListAPIView):
    serializer_class = CompanyMemberSerializer

    def get_queryset(self):
        return CompanyMember.objects.filter(
            company_id=self.kwargs["pk"]
        ).select_related("user", "company")


class InviteMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCompanyOwnerOrAdmin]

    def post(self, request, pk):
        company = Company.objects.get(pk=pk)
        self.check_object_permissions(request, company)
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = invite_member(
            company=company,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            invited_by=request.user,
            request=request,
        )
        return Response(CompanyMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class UpdateRemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCompanyOwnerOrAdmin]

    def patch(self, request, pk, member_id):
        company = Company.objects.get(pk=pk)
        self.check_object_permissions(request, company)
        member = CompanyMember.objects.get(pk=member_id, company=company)
        serializer = UpdateMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = update_member_role(
            member=member,
            role=serializer.validated_data["role"],
            updated_by=request.user,
            request=request,
        )
        return Response(CompanyMemberSerializer(member).data)

    def delete(self, request, pk, member_id):
        company = Company.objects.get(pk=pk)
        self.check_object_permissions(request, company)
        member = CompanyMember.objects.get(pk=member_id, company=company)
        remove_member(member=member, removed_by=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
