from __future__ import annotations

import logging
from dataclasses import dataclass
from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from customers.models import Company, TenantEmailConfig

logger = logging.getLogger(__name__)


class TenantEmailServiceError(Exception):
    """Raised when tenant email delivery cannot be performed safely."""


@dataclass(frozen=True)
class _ResolvedEmailConfig:
    backend: str
    host: str | None
    port: int | None
    username: str | None
    password: str | None
    use_tls: bool
    use_ssl: bool
    from_email: str
    reply_to: list[str]


class EmailService:
    """Tenant-aware SMTP email sender with optional global fallback."""

    SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

    def __init__(self, *, allow_global_fallback: bool | None = None):
        self.allow_global_fallback = (
            bool(allow_global_fallback)
            if allow_global_fallback is not None
            else bool(getattr(settings, "TENANT_EMAIL_ALLOW_GLOBAL_FALLBACK", True))
        )

    def resolve_config(self, company: Company) -> TenantEmailConfig | None:
        return TenantEmailConfig.objects.filter(company=company).first()

    def send_email(
        self,
        *,
        company: Company,
        to_list: list[str],
        subject: str,
        text: str,
        html: str = "",
    ) -> int:
        if not to_list:
            raise TenantEmailServiceError("Recipient list cannot be empty.")

        resolved = self._resolve_delivery(company)
        connection = get_connection(
            backend=resolved.backend,
            host=resolved.host,
            port=resolved.port,
            username=resolved.username,
            password=resolved.password,
            use_tls=resolved.use_tls,
            use_ssl=resolved.use_ssl,
            fail_silently=False,
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=resolved.from_email,
            to=to_list,
            reply_to=resolved.reply_to,
            connection=connection,
        )
        if html:
            message.attach_alternative(html, "text/html")

        sent_count = message.send(fail_silently=False)

        logger.info(
            "Tenant email sent",
            extra={
                "company_id": company.id,
                "tenant_code": company.tenant_code,
                "to_count": len(to_list),
                "smtp_host": resolved.host or "<default>",
                "smtp_port": resolved.port,
            },
        )
        return sent_count

    def _resolve_delivery(self, company: Company) -> _ResolvedEmailConfig:
        tenant_config = self.resolve_config(company)

        if tenant_config and tenant_config.is_enabled:
            from_email = self._build_from_email(
                tenant_config.default_from_name,
                tenant_config.default_from_email,
            )
            if not from_email:
                from_email = self._build_from_email(
                    getattr(settings, "DEFAULT_FROM_NAME", ""),
                    getattr(settings, "DEFAULT_FROM_EMAIL", ""),
                )
            if not from_email:
                raise TenantEmailServiceError(
                    "Tenant SMTP is enabled, but no default sender email is configured."
                )
            reply_to = [tenant_config.reply_to_email] if tenant_config.reply_to_email else []
            return _ResolvedEmailConfig(
                backend=self.SMTP_BACKEND,
                host=tenant_config.smtp_host,
                port=int(tenant_config.smtp_port),
                username=tenant_config.smtp_username or None,
                password=tenant_config.smtp_password or None,
                use_tls=bool(tenant_config.smtp_use_tls),
                use_ssl=bool(tenant_config.smtp_use_ssl),
                from_email=from_email,
                reply_to=reply_to,
            )

        if not self.allow_global_fallback:
            raise TenantEmailServiceError("Tenant SMTP configuration is missing or disabled.")

        default_from = self._build_from_email(
            getattr(settings, "DEFAULT_FROM_NAME", ""),
            getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        )
        if not default_from:
            raise TenantEmailServiceError("Global email fallback is enabled, but DEFAULT_FROM_EMAIL is empty.")

        logger.warning(
            "Using global email fallback for tenant delivery",
            extra={"company_id": company.id, "tenant_code": company.tenant_code},
        )
        return _ResolvedEmailConfig(
            backend=getattr(settings, "EMAIL_BACKEND", self.SMTP_BACKEND),
            host=getattr(settings, "EMAIL_HOST", None),
            port=getattr(settings, "EMAIL_PORT", None),
            username=getattr(settings, "EMAIL_HOST_USER", None),
            password=getattr(settings, "EMAIL_HOST_PASSWORD", None),
            use_tls=bool(getattr(settings, "EMAIL_USE_TLS", False)),
            use_ssl=bool(getattr(settings, "EMAIL_USE_SSL", False)),
            from_email=default_from,
            reply_to=[],
        )

    @staticmethod
    def _build_from_email(from_name: str, from_email: str) -> str:
        safe_name = (from_name or "").strip()
        safe_email = (from_email or "").strip()
        if not safe_email:
            return ""
        if not safe_name:
            return safe_email
        return formataddr((safe_name, safe_email))
