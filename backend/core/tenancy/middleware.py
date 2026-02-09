from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import JsonResponse

from customers.models import Company
from tenancy.context import reset_current_company, set_current_company

try:  # pragma: no cover - import guard for legacy mode / minimal envs
    from django.urls import set_urlconf
    from django_tenants.middleware.main import TenantMainMiddleware
    from django_tenants.utils import get_public_schema_name, get_tenant_domain_model
except Exception:  # pragma: no cover - django-tenants not available/active
    TenantMainMiddleware = object  # type: ignore[misc,assignment]
    get_public_schema_name = lambda: "public"  # noqa: E731
    get_tenant_domain_model = lambda: None  # noqa: E731
    set_urlconf = lambda _urlconf: None  # noqa: E731


class MksTenantMainMiddleware(TenantMainMiddleware):
    """Schema-per-tenant middleware (django-tenants).

    Rules:
    - `sistema.<base_domain>` (control plane) always stays in `public`.
    - Tenant schemas resolve via `customers.Domain` (explicit mapping).
    - Local/dev (`localhost`, `127.0.0.1`, `testserver`) can use `X-Tenant-ID` header
      for convenience when no subdomain is available.
    """

    TENANT_NOT_FOUND_STATUS = 404

    def __init__(self, get_response):
        super().__init__(get_response)
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
        if self.control_plane_host:
            self.public_hosts.add(self.control_plane_host)

    def process_request(self, request):
        # Tenant metadata is stored in the public schema.
        connection.set_schema_to_public()

        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            return JsonResponse({"detail": "Invalid host."}, status=400)

        # Local/dev: allow header-based tenant selection.
        if hostname in {"localhost", "127.0.0.1", "testserver"}:
            header_value = (request.headers.get(self.tenant_id_header) or "").strip().lower()
            if header_value and self._path_requires_tenant(request.path):
                tenant = (
                    Company.objects.filter(
                        tenant_code=header_value,
                        is_active=True,
                    )
                    .only("id", "tenant_code", "schema_name", "rbac_overrides")
                    .first()
                )
                if tenant is None:
                    return JsonResponse(
                        {"detail": "Invalid tenant identifier."},
                        status=self.TENANT_NOT_FOUND_STATUS,
                    )

                request.tenant = tenant
                tenant.domain_url = hostname
                connection.set_tenant(tenant)
                self.setup_url_routing(request, force_public=False)
                return None

            # No tenant header: keep public schema (auth + control plane APIs).
            connection.set_schema_to_public()
            self.setup_url_routing(request, force_public=True)
            return None

        # Control plane + explicit public hosts always stay public.
        if hostname in self.public_hosts:
            connection.set_schema_to_public()
            self.setup_url_routing(request, force_public=True)
            return None

        # Production tenant hosts: require explicit domain mapping.
        domain_model = get_tenant_domain_model()
        try:
            tenant = self.get_tenant(domain_model, hostname)
        except Exception:
            return JsonResponse(
                {"detail": "Tenant not found for hostname."},
                status=self.TENANT_NOT_FOUND_STATUS,
            )

        if not getattr(tenant, "is_active", True):
            return JsonResponse({"detail": "Tenant is inactive."}, status=403)

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(tenant)
        self.setup_url_routing(request, force_public=False)
        return None

    @staticmethod
    def setup_url_routing(request, force_public=False):
        """Ensure urlconf is set for both public and tenant schemas."""

        public_schema = get_public_schema_name()
        tenant = getattr(request, "tenant", None)
        is_public = force_public or tenant is None or getattr(tenant, "schema_name", "") == public_schema

        if is_public and hasattr(settings, "PUBLIC_SCHEMA_URLCONF"):
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
        else:
            request.urlconf = settings.ROOT_URLCONF

        set_urlconf(request.urlconf)

    def _path_requires_tenant(self, path: str) -> bool:
        if not path.startswith(self.required_path_prefixes):
            return False
        if path.startswith(self.exempt_path_prefixes):
            return False
        return True


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

        # Local/dev hosts are allowed to hit both portal surfaces.
        if host in {"localhost", "127.0.0.1", "testserver"}:
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
        if getattr(settings, "DJANGO_TENANTS_ENABLED", False):
            return self._resolve_company_from_django_tenants(request)

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

    def _resolve_company_from_django_tenants(self, request) -> TenantResolutionResult:
        """Bridge `django-tenants` into our request-scoped tenant context.

        - Tenant schema: `request.tenant` is a `customers.Company`.
        - Public schema: `request.tenant` may be missing; tenant-required endpoints must 400.
        - If `X-Tenant-ID` header is present, enforce it matches the resolved tenant.
        """

        if request.path.startswith(self.exempt_path_prefixes):
            return TenantResolutionResult(company=None)

        if not request.path.startswith(self.required_path_prefixes):
            return TenantResolutionResult(company=None)

        public_schema = "public"
        try:
            public_schema = get_public_schema_name()
        except Exception:  # pragma: no cover - defensive
            public_schema = "public"

        tenant = getattr(request, "tenant", None)
        company = None
        if tenant is not None and getattr(tenant, "schema_name", public_schema) != public_schema:
            company = tenant

        header_value = request.headers.get(self.tenant_id_header, "").strip().lower()
        if header_value and company is not None and company.tenant_code != header_value:
            return TenantResolutionResult(
                company=None,
                error_response=JsonResponse(
                    {"detail": "Tenant mismatch between host and header."},
                    status=400,
                ),
            )

        if company is None:
            return TenantResolutionResult(
                company=None,
                error_response=JsonResponse(
                    {"detail": "Tenant not provided. Send X-Tenant-ID or use tenant subdomain."},
                    status=400,
                ),
            )

        return TenantResolutionResult(company=company)

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
