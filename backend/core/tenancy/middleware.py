from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.http import JsonResponse

from customers.models import Company
from tenancy.context import reset_current_company, set_current_company


@dataclass(frozen=True)
class TenantResolutionResult:
    company: Optional[Company]
    error_response: Optional[JsonResponse] = None


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.tenant_id_header = getattr(settings, "TENANT_ID_HEADER", "X-Tenant-ID")
        self.required_path_prefixes = tuple(
            getattr(settings, "TENANT_REQUIRED_PATH_PREFIXES", ["/api/"])
        )
        self.exempt_path_prefixes = tuple(
            getattr(
                settings,
                "TENANT_EXEMPT_PATH_PREFIXES",
                ["/api/auth/token/", "/api/auth/me/"],
            )
        )
        self.control_plane_host = getattr(settings, "CONTROL_PLANE_HOST", "").strip().lower()
        self.public_hosts = set(
            host.lower() for host in getattr(settings, "TENANT_PUBLIC_HOSTS", [])
        )
        self.reserved_subdomains = set(
            subdomain.lower()
            for subdomain in getattr(settings, "TENANT_RESERVED_SUBDOMAINS", [])
        )
        self.base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "").lower()

    def __call__(self, request):
        portal_access = self._ensure_portal_access(request)
        if portal_access is not None:
            return portal_access

        tenant_resolution = self._resolve_company(request)

        if tenant_resolution.error_response is not None:
            return tenant_resolution.error_response

        token = set_current_company(tenant_resolution.company)
        request.company = tenant_resolution.company
        try:
            return self.get_response(request)
        finally:
            reset_current_company(token)

    def _ensure_portal_access(self, request) -> Optional[JsonResponse]:
        """Hard separation between Control Plane and Tenant portals.

        - `/platform/api/*` must only be called from the Control Plane host (sistema.*).
        - `/api/*` (tenant APIs) must not be called from the Control Plane host.

        This prevents accidental portal mixing and reduces data-leakage risk due to
        misrouted requests or misconfigured frontend routing.
        """

        host = (request.get_host() or "").split(":", 1)[0].strip().lower()
        if not host:
            return None

        # Local/dev and explicitly-public hosts are allowed to hit both portal surfaces.
        if host in self.public_hosts or host.endswith(".localhost"):
            return None

        is_control_plane_host = bool(self.control_plane_host) and host == self.control_plane_host

        # Tenant hosts are any non-reserved subdomains under the base domain.
        tenant_subdomain = self._extract_subdomain(host)
        is_tenant_host = (
            tenant_subdomain is not None
            and tenant_subdomain not in self.reserved_subdomains
            and not is_control_plane_host
        )

        if request.path.startswith("/platform/api/") and is_tenant_host:
            return JsonResponse(
                {"detail": "Control Plane API is not available on tenant hosts."},
                status=403,
            )

        if request.path.startswith("/api/") and is_control_plane_host:
            if request.path.startswith(self.exempt_path_prefixes):
                return None
            return JsonResponse(
                {"detail": "Tenant API is not available on the Control Plane host."},
                status=403,
            )

        return None

    def _resolve_company(self, request) -> TenantResolutionResult:
        if request.path.startswith(self.exempt_path_prefixes):
            return TenantResolutionResult(company=None)

        if not request.path.startswith(self.required_path_prefixes):
            return TenantResolutionResult(company=None)

        header_value = request.headers.get(self.tenant_id_header, "").strip().lower()
        host_company = self._company_from_host(request.get_host())

        if header_value:
            header_company = (
                Company.objects.filter(
                    tenant_code=header_value,
                    is_active=True,
                )
                .only("id", "tenant_code", "rbac_overrides")
                .first()
            )
            if header_company is None:
                return TenantResolutionResult(
                    company=None,
                    error_response=JsonResponse(
                        {"detail": "Invalid tenant identifier."},
                        status=404,
                    ),
                )

            if host_company is not None and host_company.id != header_company.id:
                return TenantResolutionResult(
                    company=None,
                    error_response=JsonResponse(
                        {"detail": "Tenant mismatch between host and header."},
                        status=400,
                    ),
                )

            return TenantResolutionResult(company=header_company)

        if host_company is not None:
            return TenantResolutionResult(company=host_company)

        return TenantResolutionResult(
            company=None,
            error_response=JsonResponse(
                {"detail": "Tenant not provided. Send X-Tenant-ID or use tenant subdomain."},
                status=400,
            ),
        )

    def _company_from_host(self, host_with_port: str) -> Optional[Company]:
        host = host_with_port.split(":", 1)[0].lower()
        if not host or host in self.public_hosts:
            return None

        subdomain = self._extract_subdomain(host)
        if not subdomain:
            return None
        if subdomain in self.reserved_subdomains:
            return None

        return (
            Company.objects.filter(
                subdomain=subdomain,
                is_active=True,
            )
            .only("id", "tenant_code", "rbac_overrides")
            .first()
        )

    def _extract_subdomain(self, host: str) -> Optional[str]:
        if self.base_domain:
            suffix = self.base_domain
            if not suffix.startswith("."):
                suffix = f".{suffix}"

            if host.endswith(suffix):
                subdomain = host[: -len(suffix)]
                if subdomain and "." not in subdomain:
                    return subdomain
                return None

        if host.endswith(".localhost"):
            local_subdomain = host.split(".", 1)[0]
            return local_subdomain if local_subdomain else None

        parts = host.split(".")
        if len(parts) >= 3:
            return parts[0]

        return None
