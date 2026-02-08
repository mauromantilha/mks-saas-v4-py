from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import CompanyMembership
from customers.serializers import (
    CompanyMembershipReadSerializer,
    CompanyMembershipUpdateSerializer,
    CompanyMembershipUpsertSerializer,
)
from tenancy.permissions import IsAuthenticatedTenantMember, IsTenantOwner
from tenancy.rbac import (
    get_resource_role_matrices,
    normalize_rbac_overrides,
    resource_capabilities_for_role,
    serialize_role_matrices,
    validate_rbac_overrides_schema,
)


class AuthenticatedUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = CompanyMembership.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related("company")

        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "memberships": [
                    {
                        "company_id": membership.company_id,
                        "company_name": membership.company.name,
                        "tenant_code": membership.company.tenant_code,
                        "role": membership.role,
                    }
                    for membership in memberships
                ],
            }
        )


class ActiveTenantUserAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    def get(self, request):
        membership = (
            CompanyMembership.objects.filter(
                company=request.company,
                user=request.user,
                is_active=True,
            )
            .select_related("company")
            .first()
        )
        return Response(
            {
                "user_id": request.user.id,
                "username": request.user.username,
                "company_id": request.company.id,
                "tenant_code": request.company.tenant_code,
                "role": membership.role if membership else None,
            }
        )


class TenantCapabilitiesAPIView(APIView):
    permission_classes = [IsAuthenticatedTenantMember]

    def get(self, request):
        membership = getattr(request, "tenant_membership", None)
        if membership is None:
            membership = (
                CompanyMembership.objects.filter(
                    company=request.company,
                    user=request.user,
                    is_active=True,
                )
                .only("role")
                .first()
            )

        role = membership.role if membership else None
        resource_matrices = get_resource_role_matrices(company=request.company)
        capabilities = {
            resource: resource_capabilities_for_role(role_matrix, role)
            for resource, role_matrix in resource_matrices.items()
        }

        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "role": role,
                "capabilities": capabilities,
            }
        )


class TenantRBACAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticatedTenantMember()]
        return [IsTenantOwner()]

    def get(self, request):
        return Response(self._build_payload(request.company))

    def put(self, request):
        try:
            normalized_overrides = self._extract_and_validate_overrides(request.data)
        except ValidationError as exc:
            return Response(
                {"detail": self._validation_detail(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.company.rbac_overrides = normalized_overrides
        request.company.save(update_fields=["rbac_overrides", "updated_at"])
        return Response(self._build_payload(request.company))

    def patch(self, request):
        try:
            normalized_overrides = self._extract_and_validate_overrides(request.data)
            merged_overrides = self._merge_overrides(
                request.company.rbac_overrides,
                normalized_overrides,
            )
            validate_rbac_overrides_schema(merged_overrides)
            merged_overrides = normalize_rbac_overrides(merged_overrides)
        except ValidationError as exc:
            return Response(
                {"detail": self._validation_detail(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.company.rbac_overrides = merged_overrides
        request.company.save(update_fields=["rbac_overrides", "updated_at"])
        return Response(self._build_payload(request.company))

    @staticmethod
    def _merge_overrides(current_overrides, incoming_overrides):
        merged = deepcopy(current_overrides if isinstance(current_overrides, dict) else {})
        for resource_key, method_map in incoming_overrides.items():
            current_method_map = merged.get(resource_key, {})
            if not isinstance(current_method_map, dict):
                current_method_map = {}
            merged[resource_key] = {**current_method_map, **method_map}
        return merged

    @staticmethod
    def _extract_and_validate_overrides(payload):
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")

        raw_overrides = payload.get("rbac_overrides", payload)
        if raw_overrides in (None, ""):
            raw_overrides = {}

        validate_rbac_overrides_schema(raw_overrides)
        return normalize_rbac_overrides(raw_overrides)

    @staticmethod
    def _validation_detail(exception):
        try:
            return exception.message_dict
        except (AttributeError, TypeError):
            return exception.messages

    @staticmethod
    def _build_payload(company):
        tenant_overrides = normalize_rbac_overrides(getattr(company, "rbac_overrides", {}))
        effective_matrices = serialize_role_matrices(
            get_resource_role_matrices(company=company)
        )
        return {
            "tenant_code": company.tenant_code,
            "rbac_overrides": tenant_overrides,
            "effective_role_matrices": effective_matrices,
        }


class TenantMembersAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticatedTenantMember()]
        return [IsTenantOwner()]

    def get(self, request):
        memberships = (
            CompanyMembership.objects.filter(
                company=request.company,
            )
            .select_related("user")
            .order_by("user__username")
        )
        serializer = CompanyMembershipReadSerializer(memberships, many=True)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "results": serializer.data,
            }
        )

    def post(self, request):
        serializer = CompanyMembershipUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        role = serializer.validated_data["role"]
        is_active = serializer.validated_data["is_active"]

        User = get_user_model()
        user = User.objects.filter(username=username).only("id").first()
        if user is None:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership, created = CompanyMembership.objects.update_or_create(
            company=request.company,
            user=user,
            defaults={"role": role, "is_active": is_active},
        )
        read_serializer = CompanyMembershipReadSerializer(membership)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TenantMemberDetailAPIView(APIView):
    permission_classes = [IsTenantOwner]

    def patch(self, request, membership_id):
        membership = get_object_or_404(
            CompanyMembership.objects.select_related("user"),
            id=membership_id,
            company=request.company,
        )
        serializer = CompanyMembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data.get("role", membership.role)
        is_active = serializer.validated_data.get("is_active", membership.is_active)

        if membership.user_id == request.user.id:
            if role != CompanyMembership.ROLE_OWNER:
                return Response(
                    {"detail": "Owner cannot downgrade their own role."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not is_active:
                return Response(
                    {"detail": "Owner cannot deactivate their own membership."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        membership.role = role
        membership.is_active = is_active
        membership.save(update_fields=["role", "is_active", "updated_at"])

        return Response(CompanyMembershipReadSerializer(membership).data)

    def delete(self, request, membership_id):
        membership = get_object_or_404(
            CompanyMembership.objects.select_related("user"),
            id=membership_id,
            company=request.company,
        )
        if membership.user_id == request.user.id:
            return Response(
                {"detail": "Owner cannot remove their own membership."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
