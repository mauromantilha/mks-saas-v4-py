"""Insurance Core permissions.

Currently we reuse the global tenant RBAC permission (`IsTenantRoleAllowed`) via
`tenant_resource_key` attributes on API views.

This module exists to centralize future object-level permissions (django-guardian)
and per-insurer/product special rules.
"""

