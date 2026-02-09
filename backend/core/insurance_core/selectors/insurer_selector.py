from __future__ import annotations

from insurance_core.models import Insurer


def list_insurers(*, company, status: str | None = None, search: str | None = None):
    qs = Insurer.all_objects.filter(company=company)
    if status:
        qs = qs.filter(status=str(status).strip().upper())
    if search:
        search = str(search).strip()
        if search:
            qs = qs.filter(name__icontains=search)
    return qs.order_by("name", "id")


def get_insurer(*, company, insurer_id: int) -> Insurer:
    return Insurer.all_objects.get(company=company, id=insurer_id)

