import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import DisallowedHost
from django.apps import apps
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone

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
        self.logger = logging.getLogger(__name__)
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
        self.suspension_exempt_path_prefixes = tuple(
            getattr(
                settings,
                "TENANT_SUSPENSION_EXEMPT_PATH_PREFIXES",
                [
                    "/api/auth/token/",
                    "/api/auth/password-reset/request/",
                    "/api/auth/password-reset/confirm/",
                ],
            )
        )
        self.control_plane_host = getattr(settings, "CONTROL_PLANE_HOST", "").strip().lower()
        self.public_hosts = set(
            host.lower() for host in getattr(settings, "TENANT_PUBLIC_HOSTS", [])
        )
        if self.control_plane_host:
            self.public_hosts.add(self.control_plane_host)

    def process_request(self, request):
        request.correlation_id = self._resolve_correlation_id(request)
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
                try:
                    control_tenant = tenant.control_tenant
                except Exception:
                    control_tenant = None
                if control_tenant is not None and control_tenant.status != "ACTIVE":
                    if not request.path.startswith(self.suspension_exempt_path_prefixes):
                        reason = self._build_status_reason(control_tenant.status, control_tenant)
                        return self._tenant_blocked_response(
                            request=request,
                            tenant=tenant,
                            detail=reason["detail"],
                            http_status=reason["status_code"],
                            reason_code=reason["reason_code"],
                            status_value=control_tenant.status,
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
            return self._tenant_blocked_response(
                request=request,
                tenant=tenant,
                detail="Tenant is inactive.",
                http_status=403,
                reason_code="INACTIVE",
            )
        try:
            control_tenant = tenant.control_tenant
        except Exception:
            control_tenant = None
        if control_tenant is not None and control_tenant.status != "ACTIVE":
            if request.path.startswith(self.suspension_exempt_path_prefixes):
                return None
            reason = self._build_status_reason(control_tenant.status, control_tenant)
            return self._tenant_blocked_response(
                request=request,
                tenant=tenant,
                detail=reason["detail"],
                http_status=reason["status_code"],
                reason_code=reason["reason_code"],
                status_value=control_tenant.status,
            )

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

    @staticmethod
    def _resolve_correlation_id(request) -> str:
        header_value = (request.headers.get("X-Correlation-ID", "") or "").strip()
        return header_value or str(uuid.uuid4())

    def _tenant_blocked_response(
        self,
        request,
        tenant,
        detail: str,
        http_status: int,
        reason_code: str,
        status_value: str = "",
    ) -> JsonResponse:
        payload = {
            "detail": detail,
            "reason": reason_code,
            "correlation_id": request.correlation_id,
        }
        response = JsonResponse(payload, status=http_status)
        response["X-Correlation-ID"] = request.correlation_id
        self.logger.warning(
            "tenant request blocked",
            extra={
                "correlation_id": request.correlation_id,
                "tenant_id": getattr(tenant, "id", None),
                "tenant_status": status_value,
                "reason": reason_code,
                "path": request.path,
            },
        )
        return response

    @staticmethod
    def _build_status_reason(status_value: str, control_tenant):
        latest_reason = (
            control_tenant.status_history.order_by("-created_at").values_list("reason", flat=True).first()
            or ""
        )
        normalized = (status_value or "").upper()
        if normalized == "SUSPENDED":
            return {
                "detail": f"Tenant is suspended. {latest_reason}".strip(),
                "reason_code": "SUSPENDED",
                "status_code": 423,
            }
        if normalized == "CANCELLED":
            return {
                "detail": f"Tenant is cancelled. {latest_reason}".strip(),
                "reason_code": "CANCELLED",
                "status_code": 423,
            }
        if normalized == "DELETED":
            return {
                "detail": "Tenant is deleted.",
                "reason_code": "DELETED",
                "status_code": 423,
            }
        return {
            "detail": "Tenant is inactive.",
            "reason_code": "INACTIVE",
            "status_code": 403,
        }


@dataclass(frozen=True)
class TenantResolutionResult:
    company: Optional[Company]
    error_response: Optional[JsonResponse] = None


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)
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
        self.suspension_exempt_path_prefixes = tuple(
            getattr(
                settings,
                "TENANT_SUSPENSION_EXEMPT_PATH_PREFIXES",
                [
                    "/api/auth/token/",
                    "/api/auth/password-reset/request/",
                    "/api/auth/password-reset/confirm/",
                ],
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
        request.correlation_id = self._resolve_correlation_id(request)
        portal_access = self._ensure_portal_access(request)
        if portal_access is not None:
            portal_access["X-Correlation-ID"] = request.correlation_id
            return portal_access

        tenant_resolution = self._resolve_company(request)

        if tenant_resolution.error_response is not None:
            tenant_resolution.error_response["X-Correlation-ID"] = request.correlation_id
            return tenant_resolution.error_response

        token = set_current_company(tenant_resolution.company)
        request.company = tenant_resolution.company
        try:
            rate_limit_response = self._enforce_tenant_rate_limit(request, tenant_resolution.company)
            if rate_limit_response is not None:
                rate_limit_response["X-Correlation-ID"] = request.correlation_id
                return rate_limit_response

            response = self.get_response(request)
            response["X-Correlation-ID"] = request.correlation_id
            return response
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

        if request.path.startswith("/api/control-panel/") and is_tenant_host:
            return JsonResponse(
                {"detail": "Control Panel API is not available on tenant hosts."},
                status=403,
            )

        if request.path.startswith("/api/") and is_control_plane_host:
            if request.path.startswith(self.exempt_path_prefixes):
                return None
            if request.path.startswith("/api/control-panel/"):
                return None
            return JsonResponse(
                {"detail": "Tenant API is not available on the Control Plane host."},
                status=403,
            )

        return None

    def _resolve_company(self, request) -> TenantResolutionResult:
        if getattr(settings, "DJANGO_TENANTS_ENABLED", False):
            return self._resolve_company_from_django_tenants(request)

        if request.path.startswith("/platform/api/") or request.path.startswith("/api/control-panel/"):
            return TenantResolutionResult(company=None)

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

            return self._validate_company_access(request, header_company)

        if host_company is not None:
            return self._validate_company_access(request, host_company)

        return TenantResolutionResult(
            company=None,
            error_response=JsonResponse(
                {"detail": "Tenant not provided. Send X-Tenant-ID or use tenant subdomain."},
                status=400,
            ),
        )

    def _validate_company_access(self, request, company: Company) -> TenantResolutionResult:
        try:
            control_tenant = company.control_tenant
        except Exception:
            control_tenant = None

        if control_tenant is None or control_tenant.status == "ACTIVE":
            return TenantResolutionResult(company=company)

        if request.path.startswith(self.suspension_exempt_path_prefixes):
            return TenantResolutionResult(company=company)

        reason = self._build_status_reason(control_tenant.status, control_tenant)
        self.logger.warning(
            "tenant request blocked",
            extra={
                "correlation_id": request.correlation_id,
                "tenant_id": company.id,
                "tenant_status": control_tenant.status,
                "reason": reason["reason_code"],
                "path": request.path,
            },
        )
        return TenantResolutionResult(
            company=None,
            error_response=JsonResponse(
                {
                    "detail": reason["detail"],
                    "reason": reason["reason_code"],
                    "correlation_id": request.correlation_id,
                },
                status=reason["status_code"],
            ),
        )

    def _resolve_company_from_django_tenants(self, request) -> TenantResolutionResult:
        """Bridge `django-tenants` into our request-scoped tenant context.

        - Tenant schema: `request.tenant` is a `customers.Company`.
        - Public schema: `request.tenant` may be missing; tenant-required endpoints must 400.
        - If `X-Tenant-ID` header is present, enforce it matches the resolved tenant.
        """

        if request.path.startswith("/platform/api/") or request.path.startswith("/api/control-panel/"):
            return TenantResolutionResult(company=None)

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

        try:
            control_tenant = company.control_tenant
        except Exception:
            control_tenant = None
        if control_tenant is not None and control_tenant.status != "ACTIVE":
            if request.path.startswith(self.suspension_exempt_path_prefixes):
                return TenantResolutionResult(company=company)
            reason = self._build_status_reason(control_tenant.status, control_tenant)
            self.logger.warning(
                "tenant request blocked",
                extra={
                    "correlation_id": request.correlation_id,
                    "tenant_id": company.id,
                    "tenant_status": control_tenant.status,
                    "reason": reason["reason_code"],
                    "path": request.path,
                },
            )
            return TenantResolutionResult(
                company=None,
                error_response=JsonResponse(
                    {
                        "detail": reason["detail"],
                        "reason": reason["reason_code"],
                        "correlation_id": request.correlation_id,
                    },
                    status=reason["status_code"],
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

    @staticmethod
    def _resolve_correlation_id(request) -> str:
        header_value = (request.headers.get("X-Correlation-ID", "") or "").strip()
        return header_value or str(uuid.uuid4())

    @staticmethod
    def _build_status_reason(status_value: str, control_tenant):
        latest_reason = (
            control_tenant.status_history.order_by("-created_at").values_list("reason", flat=True).first()
            or ""
        )
        normalized = (status_value or "").upper()
        if normalized == "SUSPENDED":
            return {
                "detail": f"Tenant is suspended. {latest_reason}".strip(),
                "reason_code": "SUSPENDED",
                "status_code": 423,
            }
        if normalized == "CANCELLED":
            return {
                "detail": f"Tenant is cancelled. {latest_reason}".strip(),
                "reason_code": "CANCELLED",
                "status_code": 423,
            }
        if normalized == "DELETED":
            return {
                "detail": "Tenant is deleted.",
                "reason_code": "DELETED",
                "status_code": 423,
            }
        return {
            "detail": "Tenant is inactive.",
            "reason_code": "INACTIVE",
            "status_code": 403,
        }

    def _enforce_tenant_rate_limit(self, request, company: Optional[Company]) -> Optional[JsonResponse]:
        if company is None:
            return None
        if not request.path.startswith(self.required_path_prefixes):
            return None
        if request.path.startswith(self.exempt_path_prefixes):
            return None

        tenant_settings_model = apps.get_model("control_plane", "TenantOperationalSettings")
        tenant_alert_model = apps.get_model("control_plane", "TenantAlertEvent")
        if tenant_settings_model is None:
            return None

        settings_obj = (
            tenant_settings_model.objects.filter(tenant__company=company)
            .only("requests_per_minute")
            .first()
        )
        requests_per_minute = int(getattr(settings_obj, "requests_per_minute", 600))
        if requests_per_minute <= 0:
            return None

        now = timezone.now()
        bucket = now.strftime("%Y%m%d%H%M")
        cache_ttl = max(5, int(getattr(settings, "TENANT_RATE_LIMIT_CACHE_SECONDS", 70)))
        rate_key = f"tenant:rate-limit:{company.id}:{bucket}"

        added = cache.add(rate_key, 1, timeout=cache_ttl)
        if added:
            current_count = 1
        else:
            try:
                current_count = cache.incr(rate_key)
            except Exception:
                cache.set(rate_key, 1, timeout=cache_ttl)
                current_count = 1

        if current_count <= requests_per_minute:
            return None

        alert_cache_key = f"tenant:rate-limit-alert:{company.id}:{bucket}"
        if cache.add(alert_cache_key, 1, timeout=cache_ttl) and tenant_alert_model is not None:
            tenant = getattr(company, "control_tenant", None)
            if tenant is not None:
                try:
                    tenant_alert_model.objects.get_or_create(
                        tenant=tenant,
                        alert_type="RATE_LIMIT_EXCEEDED",
                        status="OPEN",
                        defaults={
                            "severity": "WARNING",
                            "message": (
                                f"Rate limit exceeded ({current_count}/{requests_per_minute} rpm)."
                            ),
                            "metrics_json": {
                                "requests_per_minute": requests_per_minute,
                                "observed_requests": current_count,
                                "bucket": bucket,
                            },
                        },
                    )
                except Exception:
                    self.logger.exception(
                        "failed to register tenant rate-limit alert",
                        extra={
                            "tenant_id": getattr(tenant, "id", None),
                            "correlation_id": getattr(request, "correlation_id", ""),
                        },
                    )

        self.logger.warning(
            "tenant rate-limit exceeded",
            extra={
                "correlation_id": getattr(request, "correlation_id", ""),
                "tenant_id": company.id,
                "path": request.path,
                "limit": requests_per_minute,
                "observed": current_count,
            },
        )
        return JsonResponse(
            {
                "detail": "Tenant rate limit exceeded. Please retry later.",
                "reason": "RATE_LIMIT_EXCEEDED",
                "limit": requests_per_minute,
                "observed": current_count,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
            status=429,
        )
