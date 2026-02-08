# Control Plane + Tenant Portal

## Separation model

- `Control Plane` (platform admin only): tenant lifecycle, contracts, provisioning metadata.
- `Tenant Portal` (tenant members): CRM flows (`/api/*`) scoped by tenant context.

## Control Plane endpoints

- `GET /platform/api/tenants/`
- `POST /platform/api/tenants/`
- `GET /platform/api/tenants/{company_id}/`
- `PATCH /platform/api/tenants/{company_id}/`
- `POST /platform/api/tenants/{company_id}/provision/`
- `POST /platform/api/tenants/{company_id}/provision/execute/`

Authentication:

- Token/session auth required.
- Only users with `is_staff=True` or `is_superuser=True` can access.
- Endpoints can be restricted by host via `CONTROL_PLANE_ALLOWED_HOSTS` (recommended:
  `sistema.mksbrasil.com` in production).

## Domain and subdomain routing

- Base domain: `TENANT_BASE_DOMAIN` (for this project: `mksbrasil.com`).
- Control Plane host:
  - `CONTROL_PLANE_SUBDOMAIN=sistema`
  - `CONTROL_PLANE_HOST=sistema.mksbrasil.com`
- Tenant portal host pattern: `{subdomain}.mksbrasil.com`.
- Reserved subdomains blocked for tenant creation: `TENANT_RESERVED_SUBDOMAINS`
  (must include `sistema`).
- Public/non-tenant hosts: `TENANT_PUBLIC_HOSTS` (must include `sistema.mksbrasil.com`).

## Provisioning metadata

`TenantProvisioning` stores per-tenant infrastructure metadata:

- isolation model (`DATABASE_PER_TENANT` or `SHARED_SCHEMA`)
- DB alias, name, host, port, user
- secret reference for DB password
- status (`PENDING`, `PROVISIONING`, `READY`, `FAILED`)
- portal URL

This is the base to automate Cloud SQL provisioning and per-tenant database routing.

## Provisioning execution

`/provision/execute/` runs the configured provider (`CONTROL_PLANE_PROVISIONER`) and updates:

- `status` -> `PROVISIONING` -> `READY` or `FAILED`
- `provisioned_at`
- `last_error`
- `portal_url` (auto-generated from `CONTROL_PLANE_PORTAL_URL_TEMPLATE` or
  `https://{subdomain}.{TENANT_BASE_DOMAIN}` when template is empty)

Supported providers:

- `noop` (default): validation-only, safe for local/dev and CI.
- `local_postgres`: creates role/database in local PostgreSQL using admin credentials.
- `cloudsql_postgres`: creates role/database in Cloud SQL for PostgreSQL using admin credentials.

Main settings:

- `CONTROL_PLANE_PROVISIONER`
- `CONTROL_PLANE_PORTAL_URL_TEMPLATE`
- `TENANT_BASE_DOMAIN`
- `TENANT_RESERVED_SUBDOMAINS`
- `CONTROL_PLANE_SUBDOMAIN`
- `CONTROL_PLANE_HOST`
- `CONTROL_PLANE_ALLOWED_HOSTS`
- `CONTROL_PLANE_LOCAL_DB_ADMIN_DATABASE`
- `CONTROL_PLANE_LOCAL_DB_ADMIN_USER`
- `CONTROL_PLANE_LOCAL_DB_ADMIN_PASSWORD`
- `CONTROL_PLANE_LOCAL_DB_ADMIN_HOST`
- `CONTROL_PLANE_LOCAL_DB_ADMIN_PORT`
- `CONTROL_PLANE_LOCAL_DB_PASSWORD_DEFAULT`
- `CONTROL_PLANE_CLOUDSQL_ADMIN_DATABASE`
- `CONTROL_PLANE_CLOUDSQL_ADMIN_USER`
- `CONTROL_PLANE_CLOUDSQL_ADMIN_PASSWORD`
- `CONTROL_PLANE_CLOUDSQL_ADMIN_HOST` (`/cloudsql/<project>:<region>:<instance>` for unix socket mode)
- `CONTROL_PLANE_CLOUDSQL_ADMIN_PORT`
- `CONTROL_PLANE_CLOUDSQL_ADMIN_SSLMODE`
- `CONTROL_PLANE_CLOUDSQL_TENANT_PASSWORD_DEFAULT`

## Next step for cloud DB-per-tenant runtime

1. Provision a dedicated Cloud SQL database + user on tenant creation.
2. Run tenant migrations on the dedicated database.
3. Add dynamic connection routing middleware/router using `database_alias`.
4. Keep `CompanyMembership` + tenant context for auth and capability checks.
