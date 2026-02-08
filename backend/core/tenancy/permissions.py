from rest_framework.permissions import BasePermission

from customers.models import CompanyMembership
from tenancy.rbac import DEFAULT_TENANT_ROLE_MATRIX, get_role_matrix_for_resource


class IsAuthenticatedTenantMember(BasePermission):
    message = "User is not an active member of the current tenant."

    def has_permission(self, request, view):
        user = request.user
        company = getattr(request, "company", None)

        if not user or not user.is_authenticated:
            return False

        if company is None:
            return False

        if user.is_superuser:
            return True

        membership = (
            CompanyMembership.objects.filter(
                company=company,
                user=user,
                is_active=True,
            )
            .only("id", "role")
            .first()
        )
        request.tenant_membership = membership
        return membership is not None


class IsTenantRoleAllowed(BasePermission):
    message = "User role is not allowed for this action in the current tenant."

    def has_permission(self, request, view):
        user = request.user
        company = getattr(request, "company", None)

        if not user or not user.is_authenticated:
            return False

        if company is None:
            return False

        if user.is_superuser:
            return True

        membership = (
            CompanyMembership.objects.filter(
                company=company,
                user=user,
                is_active=True,
            )
            .only("id", "role")
            .first()
        )
        request.tenant_membership = membership
        if membership is None:
            return False

        role_matrix = getattr(view, "tenant_role_matrix", None)
        if role_matrix is None:
            resource_key = getattr(view, "tenant_resource_key", None)
            if resource_key:
                role_matrix = get_role_matrix_for_resource(resource_key, company=company)
            else:
                role_matrix = DEFAULT_TENANT_ROLE_MATRIX

        allowed_roles = role_matrix.get(request.method, role_matrix.get("*", frozenset()))
        return membership.role in allowed_roles


class IsTenantOwner(BasePermission):
    message = "Only OWNER users can manage tenant RBAC settings."

    def has_permission(self, request, view):
        user = request.user
        company = getattr(request, "company", None)

        if not user or not user.is_authenticated:
            return False

        if company is None:
            return False

        if user.is_superuser:
            return True

        membership = (
            CompanyMembership.objects.filter(
                company=company,
                user=user,
                is_active=True,
            )
            .only("id", "role")
            .first()
        )
        request.tenant_membership = membership
        return membership is not None and membership.role == CompanyMembership.ROLE_OWNER
