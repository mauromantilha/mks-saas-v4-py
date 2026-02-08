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
