from __future__ import annotations

from insurance_core.models import InsuranceProduct, ProductCoverage


def list_products(
    *,
    company,
    insurer_id: int | None = None,
    line_of_business: str | None = None,
    status: str | None = None,
    search: str | None = None,
):
    qs = InsuranceProduct.all_objects.filter(company=company)
    if insurer_id:
        qs = qs.filter(insurer_id=insurer_id)
    if line_of_business:
        qs = qs.filter(line_of_business=str(line_of_business).strip().upper())
    if status:
        qs = qs.filter(status=str(status).strip().upper())
    if search:
        search = str(search).strip()
        if search:
            qs = qs.filter(name__icontains=search)
    return qs.order_by("line_of_business", "name", "id")


def get_product(*, company, product_id: int) -> InsuranceProduct:
    return InsuranceProduct.all_objects.get(company=company, id=product_id)


def list_coverages(*, company, product_id: int | None = None):
    qs = ProductCoverage.all_objects.filter(company=company)
    if product_id:
        qs = qs.filter(product_id=product_id)
    return qs.order_by("product_id", "code", "id")

