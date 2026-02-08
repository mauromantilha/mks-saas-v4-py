from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from control_plane.models import TenantProvisioning


class ProvisioningExecutionError(Exception):
    pass


@dataclass(frozen=True)
class ProvisioningExecutionResult:
    success: bool
    message: str
    provider: str


class BaseTenantProvisioner:
    provider_name = "base"

    def provision(self, provisioning: TenantProvisioning) -> None:
        raise NotImplementedError


def _ensure_postgres_role_and_database(
    *,
    admin_database: str,
    admin_user: str,
    admin_password: str,
    admin_host: str,
    admin_port: int | None,
    tenant_db_user: str,
    tenant_db_name: str,
    tenant_db_password: str,
    sslmode: str | None = None,
) -> None:
    try:
        import psycopg2
        from psycopg2 import sql
    except Exception as exc:  # pragma: no cover - import guard
        raise ProvisioningExecutionError("psycopg2 is required for postgres provisioners.") from exc

    conn_kwargs = {
        "dbname": admin_database,
        "user": admin_user,
        "password": admin_password,
        "host": admin_host,
    }
    if admin_port is not None:
        conn_kwargs["port"] = admin_port
    if sslmode:
        conn_kwargs["sslmode"] = sslmode

    conn = psycopg2.connect(**conn_kwargs)
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [tenant_db_user])
            role_exists = cursor.fetchone() is not None
            if role_exists:
                cursor.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(tenant_db_user)
                    ),
                    [tenant_db_password],
                )
            else:
                cursor.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(tenant_db_user)
                    ),
                    [tenant_db_password],
                )

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [tenant_db_name])
            database_exists = cursor.fetchone() is not None
            if not database_exists:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(tenant_db_name),
                        sql.Identifier(tenant_db_user),
                    )
                )
    except Exception as exc:
        raise ProvisioningExecutionError(str(exc)) from exc
    finally:
        conn.close()


class NoopTenantProvisioner(BaseTenantProvisioner):
    provider_name = "noop"

    def provision(self, provisioning: TenantProvisioning) -> None:
        # No-op provider for local/dev and CI. It only validates required metadata.
        if not provisioning.database_alias:
            raise ProvisioningExecutionError("database_alias is required.")
        if not provisioning.database_name:
            raise ProvisioningExecutionError("database_name is required.")
        if not provisioning.database_user:
            raise ProvisioningExecutionError("database_user is required.")


class LocalPostgresTenantProvisioner(BaseTenantProvisioner):
    provider_name = "local_postgres"

    def provision(self, provisioning: TenantProvisioning) -> None:
        admin_user = getattr(settings, "CONTROL_PLANE_LOCAL_DB_ADMIN_USER", "").strip()
        admin_password = getattr(settings, "CONTROL_PLANE_LOCAL_DB_ADMIN_PASSWORD", "").strip()
        admin_host = getattr(settings, "CONTROL_PLANE_LOCAL_DB_ADMIN_HOST", "127.0.0.1")
        admin_port = getattr(settings, "CONTROL_PLANE_LOCAL_DB_ADMIN_PORT", 5432)
        admin_database = getattr(settings, "CONTROL_PLANE_LOCAL_DB_ADMIN_DATABASE", "postgres")
        tenant_password = getattr(
            settings,
            "CONTROL_PLANE_LOCAL_DB_PASSWORD_DEFAULT",
            "change-me-tenant-password",
        )

        if not admin_user or not admin_password:
            raise ProvisioningExecutionError(
                "Missing CONTROL_PLANE_LOCAL_DB_ADMIN_USER or CONTROL_PLANE_LOCAL_DB_ADMIN_PASSWORD."
            )

        _ensure_postgres_role_and_database(
            admin_database=admin_database,
            admin_user=admin_user,
            admin_password=admin_password,
            admin_host=admin_host,
            admin_port=admin_port,
            tenant_db_user=provisioning.database_user,
            tenant_db_name=provisioning.database_name,
            tenant_db_password=tenant_password,
            sslmode="disable",
        )


class CloudSQLPostgresTenantProvisioner(BaseTenantProvisioner):
    provider_name = "cloudsql_postgres"

    def provision(self, provisioning: TenantProvisioning) -> None:
        admin_user = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_USER", "").strip()
        admin_password = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD", "").strip()
        admin_database = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_DATABASE", "postgres")
        admin_host = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_HOST", "").strip()
        admin_port = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_PORT", 5432)
        sslmode = getattr(settings, "CONTROL_PLANE_CLOUDSQL_ADMIN_SSLMODE", "disable").strip()
        tenant_password = getattr(
            settings,
            "CONTROL_PLANE_CLOUDSQL_TENANT_PASSWORD_DEFAULT",
            "change-me-tenant-password",
        )

        if not admin_user or not admin_password:
            raise ProvisioningExecutionError(
                "Missing CONTROL_PLANE_CLOUDSQL_ADMIN_USER or CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD."
            )
        if not admin_host:
            raise ProvisioningExecutionError("Missing CONTROL_PLANE_CLOUDSQL_ADMIN_HOST.")

        # Unix socket mode in Cloud Run/GCE: host=/cloudsql/<project:region:instance>
        # In this case psycopg2 uses the socket path and port is ignored.
        use_socket = admin_host.startswith("/")
        _ensure_postgres_role_and_database(
            admin_database=admin_database,
            admin_user=admin_user,
            admin_password=admin_password,
            admin_host=admin_host,
            admin_port=None if use_socket else admin_port,
            tenant_db_user=provisioning.database_user,
            tenant_db_name=provisioning.database_name,
            tenant_db_password=tenant_password,
            sslmode=None if use_socket else sslmode,
        )


def get_tenant_portal_url(company) -> str:
    template = getattr(settings, "CONTROL_PLANE_PORTAL_URL_TEMPLATE", "").strip()
    if not template:
        base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "").strip().lower()
        if base_domain:
            template = f"https://{{subdomain}}.{base_domain}"
        else:
            return ""
    try:
        return template.format(
            tenant_code=company.tenant_code,
            subdomain=company.subdomain,
            company_id=company.id,
        )
    except KeyError as exc:
        raise ProvisioningExecutionError(
            f"Invalid CONTROL_PLANE_PORTAL_URL_TEMPLATE variable: {exc}."
        ) from exc


def get_tenant_provisioner() -> BaseTenantProvisioner:
    provider_name = getattr(settings, "CONTROL_PLANE_PROVISIONER", "noop").strip()
    if provider_name == "noop":
        return NoopTenantProvisioner()
    if provider_name == "local_postgres":
        return LocalPostgresTenantProvisioner()
    if provider_name == "cloudsql_postgres":
        return CloudSQLPostgresTenantProvisioner()
    raise ProvisioningExecutionError(f"Unknown control-plane provisioner '{provider_name}'.")


def execute_tenant_provisioning(company, provisioning) -> ProvisioningExecutionResult:
    provisioning.status = TenantProvisioning.STATUS_PROVISIONING
    provisioning.last_error = ""
    provisioning.save(update_fields=("status", "last_error", "updated_at"))

    provider_name = getattr(settings, "CONTROL_PLANE_PROVISIONER", "noop").strip()
    try:
        provider = get_tenant_provisioner()
        provider.provision(provisioning)
        if not provisioning.portal_url:
            generated_portal_url = get_tenant_portal_url(company)
            if generated_portal_url:
                provisioning.portal_url = generated_portal_url
        provisioning.status = TenantProvisioning.STATUS_READY
        if provisioning.provisioned_at is None:
            provisioning.provisioned_at = timezone.now()
        provisioning.last_error = ""
        provisioning.save(
            update_fields=(
                "portal_url",
                "status",
                "provisioned_at",
                "last_error",
                "updated_at",
            )
        )
        return ProvisioningExecutionResult(
            success=True,
            message="Tenant provisioning executed successfully.",
            provider=provider.provider_name,
        )
    except Exception as exc:
        provisioning.status = TenantProvisioning.STATUS_FAILED
        provisioning.last_error = str(exc)
        provisioning.save(update_fields=("status", "last_error", "updated_at"))
        return ProvisioningExecutionResult(
            success=False,
            message=str(exc),
            provider=provider_name,
        )
