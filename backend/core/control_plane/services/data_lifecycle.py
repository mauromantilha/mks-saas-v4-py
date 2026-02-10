from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from control_plane.models import Tenant


@dataclass
class PurgeResult:
    scanned: int
    purged: int


def purge_deleted_tenant_metadata(
    *,
    retention_days: int | None = None,
    apply_changes: bool = False,
) -> PurgeResult:
    days = (
        retention_days
        if retention_days is not None
        else int(getattr(settings, "CONTROL_PLANE_SOFT_DELETE_RETENTION_DAYS", 90))
    )
    cutoff = timezone.now() - timedelta(days=days)

    queryset = Tenant.objects.select_related("company").filter(
        status=Tenant.STATUS_DELETED,
        deleted_at__isnull=False,
        deleted_at__lte=cutoff,
    )
    scanned = queryset.count()
    if not apply_changes:
        return PurgeResult(scanned=scanned, purged=0)

    purged = 0
    for tenant in queryset.iterator():
        with transaction.atomic():
            tenant.legal_name = f"DELETED-TENANT-{tenant.id}"
            tenant.cnpj = ""
            tenant.cep = ""
            tenant.street = ""
            tenant.number = ""
            tenant.complement = ""
            tenant.district = ""
            tenant.city = ""
            tenant.state = ""
            tenant.save(
                update_fields=[
                    "legal_name",
                    "cnpj",
                    "cep",
                    "street",
                    "number",
                    "complement",
                    "district",
                    "city",
                    "state",
                    "updated_at",
                ]
            )

            tenant.company.name = f"Deleted Tenant {tenant.id}"
            tenant.company.save(update_fields=["name", "updated_at"])

            tenant.internal_notes.update(note="[PURGED AFTER RETENTION]")
            purged += 1

    return PurgeResult(scanned=scanned, purged=purged)
