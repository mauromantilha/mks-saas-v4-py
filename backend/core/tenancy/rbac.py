from copy import deepcopy
from typing import Iterable

from django.core.exceptions import ValidationError
from django.conf import settings

ROLE_MEMBER = "MEMBER"
ROLE_MANAGER = "MANAGER"
ROLE_OWNER = "OWNER"

VALID_ROLES = frozenset((ROLE_MEMBER, ROLE_MANAGER, ROLE_OWNER))
VALID_METHODS = frozenset(("GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "*"))

READ_ROLES = frozenset((ROLE_MEMBER, ROLE_MANAGER, ROLE_OWNER))
WRITE_ROLES = frozenset((ROLE_MANAGER, ROLE_OWNER))
OWNER_ROLES = frozenset((ROLE_OWNER,))
NO_ROLES = frozenset()


def build_role_matrix(
    *,
    read_roles=READ_ROLES,
    post_roles=WRITE_ROLES,
    put_roles=WRITE_ROLES,
    patch_roles=WRITE_ROLES,
    delete_roles=OWNER_ROLES,
):
    return {
        "GET": frozenset(read_roles),
        "HEAD": frozenset(read_roles),
        "OPTIONS": frozenset(read_roles),
        "POST": frozenset(post_roles),
        "PUT": frozenset(put_roles),
        "PATCH": frozenset(patch_roles),
        "DELETE": frozenset(delete_roles),
    }


DEFAULT_RESOURCE_ROLE_MATRICES = {
    "customers": build_role_matrix(),
    "leads": build_role_matrix(),
    "opportunities": build_role_matrix(),
    "proposal_options": build_role_matrix(),
    "policy_requests": build_role_matrix(),
    "activities": build_role_matrix(),
    "sales_goals": build_role_matrix(),
    "metrics": build_role_matrix(
        post_roles=NO_ROLES,
        put_roles=NO_ROLES,
        patch_roles=NO_ROLES,
        delete_roles=NO_ROLES,
    ),
    "dashboard": build_role_matrix(
        post_roles=NO_ROLES,
        put_roles=NO_ROLES,
        patch_roles=NO_ROLES,
        delete_roles=NO_ROLES,
    ),
    "fiscal_documents": build_role_matrix(),
    "ledger": build_role_matrix(
        read_roles=WRITE_ROLES,
        post_roles=NO_ROLES,
        put_roles=NO_ROLES,
        patch_roles=NO_ROLES,
        delete_roles=NO_ROLES,
    ),
    "apolices": build_role_matrix(
        post_roles=OWNER_ROLES,
        put_roles=OWNER_ROLES,
        patch_roles=OWNER_ROLES,
        delete_roles=OWNER_ROLES,
    ),
    "endossos": build_role_matrix(
        post_roles=OWNER_ROLES,
        put_roles=OWNER_ROLES,
        patch_roles=OWNER_ROLES,
        delete_roles=OWNER_ROLES,
    ),
    "insurers": build_role_matrix(),
    "insurance_products": build_role_matrix(),
    "product_coverages": build_role_matrix(),
    "policies": build_role_matrix(),
    "policy_items": build_role_matrix(),
    "policy_coverages": build_role_matrix(),
    "policy_document_requirements": build_role_matrix(),
    "endorsements": build_role_matrix(),
}

DEFAULT_TENANT_ROLE_MATRIX = build_role_matrix()
KNOWN_RBAC_RESOURCES = frozenset(DEFAULT_RESOURCE_ROLE_MATRICES.keys())


def _normalize_roles(raw_roles: Iterable[str]) -> frozenset[str]:
    if not isinstance(raw_roles, (list, tuple, set, frozenset)):
        return frozenset()
    normalized = {str(role).upper() for role in raw_roles}
    return frozenset(role for role in normalized if role in VALID_ROLES)


def validate_rbac_overrides_schema(overrides, *, allow_unknown_resources=False) -> None:
    if overrides in (None, {}):
        return

    if not isinstance(overrides, dict):
        raise ValidationError("rbac_overrides must be a JSON object (dictionary).")

    errors = {}
    for resource_key, method_map in overrides.items():
        resource_name = str(resource_key)
        resource_errors = []

        if not allow_unknown_resources and resource_name not in KNOWN_RBAC_RESOURCES:
            resource_errors.append(
                f"Unknown resource '{resource_name}'. Allowed: {sorted(KNOWN_RBAC_RESOURCES)}"
            )

        if not isinstance(method_map, dict):
            resource_errors.append("Resource value must be an object of HTTP methods to role lists.")
            errors[resource_name] = resource_errors
            continue

        for method, raw_roles in method_map.items():
            method_name = str(method).upper()
            if method_name not in VALID_METHODS:
                resource_errors.append(
                    f"Method '{method_name}' is invalid. Allowed: {sorted(VALID_METHODS)}"
                )
                continue

            if not isinstance(raw_roles, list) or not raw_roles:
                resource_errors.append(
                    f"Method '{method_name}' must contain a non-empty role list."
                )
                continue

            normalized_roles = _normalize_roles(raw_roles)
            if len(normalized_roles) != len(set(str(r).upper() for r in raw_roles)):
                resource_errors.append(
                    f"Method '{method_name}' contains invalid roles. "
                    f"Allowed roles: {sorted(VALID_ROLES)}"
                )

        if resource_errors:
            errors[resource_name] = resource_errors

    if errors:
        raise ValidationError(errors)


def _apply_overrides(matrices: dict, overrides: dict | None) -> dict:
    if not isinstance(overrides, dict):
        return matrices

    for resource_key, method_map in overrides.items():
        if not isinstance(method_map, dict):
            continue
        resource_name = str(resource_key)
        resource_matrix = matrices.setdefault(resource_name, {})
        for method, raw_roles in method_map.items():
            normalized_roles = _normalize_roles(raw_roles)
            if not normalized_roles:
                continue
            resource_matrix[str(method).upper()] = normalized_roles
    return matrices


def normalize_rbac_overrides(overrides: dict | None) -> dict:
    if not isinstance(overrides, dict):
        return {}

    normalized_overrides = {}
    for resource_key, method_map in overrides.items():
        if not isinstance(method_map, dict):
            continue

        normalized_method_map = {}
        for method, raw_roles in method_map.items():
            normalized_roles = sorted(_normalize_roles(raw_roles))
            if normalized_roles:
                normalized_method_map[str(method).upper()] = normalized_roles

        if normalized_method_map:
            normalized_overrides[str(resource_key)] = normalized_method_map

    return normalized_overrides


def get_resource_role_matrices(company=None) -> dict:
    matrices = deepcopy(DEFAULT_RESOURCE_ROLE_MATRICES)

    global_overrides = getattr(settings, "TENANT_ROLE_MATRICES", {})
    try:
        validate_rbac_overrides_schema(global_overrides)
        _apply_overrides(matrices, global_overrides)
    except ValidationError:
        pass

    if company is not None:
        tenant_overrides = getattr(company, "rbac_overrides", {})
        try:
            validate_rbac_overrides_schema(tenant_overrides)
            _apply_overrides(matrices, tenant_overrides)
        except ValidationError:
            pass

    return matrices


def get_role_matrix_for_resource(resource_key: str, company=None) -> dict:
    matrices = get_resource_role_matrices(company=company)
    return matrices.get(resource_key, DEFAULT_TENANT_ROLE_MATRIX)


def role_can(role_matrix, role, method):
    allowed_roles = role_matrix.get(method, role_matrix.get("*", frozenset()))
    return role in allowed_roles


def resource_capabilities_for_role(role_matrix, role):
    can_get = role_can(role_matrix, role, "GET")
    can_put = role_can(role_matrix, role, "PUT")
    can_patch = role_can(role_matrix, role, "PATCH")
    return {
        "list": can_get,
        "retrieve": can_get,
        "create": role_can(role_matrix, role, "POST"),
        "update": can_put,
        "partial_update": can_patch,
        "delete": role_can(role_matrix, role, "DELETE"),
    }


def serialize_role_matrices(resource_matrices: dict) -> dict:
    serialized = {}
    for resource_name, role_matrix in resource_matrices.items():
        serialized[resource_name] = {
            str(method).upper(): sorted(list(roles))
            for method, roles in role_matrix.items()
        }
    return serialized
