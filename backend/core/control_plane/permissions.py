from django.conf import settings
from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    message = "Only platform admins can access control-plane endpoints."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not (user.is_staff or user.is_superuser):
            return False

        allowed_hosts = {
            host.lower()
            for host in getattr(settings, "CONTROL_PLANE_ALLOWED_HOSTS", [])
            if host
        }
        if not allowed_hosts:
            return True

        request_host = request.get_host().split(":", 1)[0].lower()
        if request_host in allowed_hosts:
            return True

        self.message = "Control-plane endpoints are restricted to allowed control-plane hosts."
        return False


class IsControlPanelAdmin(IsPlatformAdmin):
    message = "Only SUPERADMIN/SAAS_ADMIN can access control-panel endpoints."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user
        if user.is_superuser:
            return True

        # Role mapping via Django groups.
        allowed_roles = {"SUPERADMIN", "SAAS_ADMIN"}
        if user.groups.filter(name__in=allowed_roles).exists():
            return True

        # Backward-compatible fallback: platform staff users can access control panel
        # when explicitly enabled (default False).
        if getattr(settings, "CONTROL_PANEL_ALLOW_STAFF_FALLBACK", False) and user.is_staff:
            return True

        self.message = "Requires SUPERADMIN or SAAS_ADMIN role."
        return False
