from __future__ import annotations

import importlib.util

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from customers.models import Company, CompanyMembership, Domain


def _guardian_enabled() -> bool:
    return importlib.util.find_spec("guardian") is not None


def _group_name(company_id: int, role: str) -> str:
    return f"tenant:{company_id}:{role.lower()}"


def _ensure_role_groups(company_id: int) -> dict[str, Group]:
    groups: dict[str, Group] = {}
    for role, _label in CompanyMembership.ROLE_CHOICES:
        group, _created = Group.objects.get_or_create(name=_group_name(company_id, role))
        groups[role] = group
    return groups


@receiver(post_save, sender=CompanyMembership)
def sync_membership_guardian_groups(sender, instance: CompanyMembership, **_kwargs):
    """Sync tenant membership into Django auth groups.

    This is the minimum viable integration for `django-guardian`:
    - Each tenant gets 3 groups (member/manager/owner).
    - Users are kept in exactly one tenant group according to their role.

    Object-level permissions can be layered later. The current API RBAC remains the
    source of truth for endpoint access.
    """

    if not _guardian_enabled():
        return

    groups_by_role = _ensure_role_groups(instance.company_id)
    user = instance.user

    # Remove from all tenant role groups for this company.
    for group in groups_by_role.values():
        user.groups.remove(group)

    # Re-add if active.
    if instance.is_active:
        target_group = groups_by_role.get(instance.role)
        if target_group is not None:
            user.groups.add(target_group)


@receiver(post_save, sender=Company)
def ensure_company_domains(sender, instance: Company, created: bool, **_kwargs):
    """Ensure a tenant has at least one Domain mapping.

    We always create a `*.localhost` domain for local development.
    If `TENANT_BASE_DOMAIN` is configured, we also create `<subdomain>.<base_domain>`.
    """

    if not created:
        return

    base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "").strip().lower()
    local_domain = f"{instance.subdomain}.localhost"
    Domain.objects.get_or_create(
        domain=local_domain,
        defaults={"tenant": instance, "is_primary": not bool(base_domain)},
    )

    if not base_domain:
        return

    public_domain = f"{instance.subdomain}.{base_domain}"
    Domain.objects.get_or_create(
        domain=public_domain,
        defaults={"tenant": instance, "is_primary": True},
    )
