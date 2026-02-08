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

Authentication:

- Token/session auth required.
- Only users with `is_staff=True` or `is_superuser=True` can access.

## Provisioning metadata

`TenantProvisioning` stores per-tenant infrastructure metadata:

- isolation model (`DATABASE_PER_TENANT` or `SHARED_SCHEMA`)
- DB alias, name, host, port, user
- secret reference for DB password
- status (`PENDING`, `PROVISIONING`, `READY`, `FAILED`)
- portal URL

This is the base to automate Cloud SQL provisioning and per-tenant database routing.

## Next step for full DB-per-tenant runtime

1. Provision a dedicated Cloud SQL database + user on tenant creation.
2. Run tenant migrations on the dedicated database.
3. Add dynamic connection routing middleware/router using `database_alias`.
4. Keep `CompanyMembership` + tenant context for auth and capability checks.
