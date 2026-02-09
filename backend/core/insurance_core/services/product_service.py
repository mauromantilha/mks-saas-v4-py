from __future__ import annotations

from django.db import transaction

from insurance_core.events import publish_tenant_event
from insurance_core.models import InsuranceProduct, ProductCoverage
from ledger.models import LedgerEntry


def _product_snapshot(product: InsuranceProduct) -> dict:
    return {
        "id": product.id,
        "insurer_id": product.insurer_id,
        "code": product.code,
        "name": product.name,
        "line_of_business": product.line_of_business,
        "status": product.status,
        "rules": product.rules,
    }


def _coverage_snapshot(coverage: ProductCoverage) -> dict:
    return {
        "id": coverage.id,
        "product_id": coverage.product_id,
        "code": coverage.code,
        "name": coverage.name,
        "coverage_type": coverage.coverage_type,
        "default_limit_amount": str(coverage.default_limit_amount),
        "default_deductible_amount": str(coverage.default_deductible_amount),
        "required": coverage.required,
    }


def upsert_product(
    *,
    company,
    actor,
    instance: InsuranceProduct | None,
    data: dict,
    request=None,
) -> InsuranceProduct:
    with transaction.atomic():
        if instance is None:
            product = InsuranceProduct(company=company, **data)
            product.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.product.create",
                resource_label="insurance_core.InsuranceProduct",
                resource_pk=str(product.pk),
                request=request,
                data_after=_product_snapshot(product),
            )
            return product

        if instance.company_id != company.id:
            raise ValueError("Cross-tenant product update blocked.")

        before = _product_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.product.update",
            resource_label="insurance_core.InsuranceProduct",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_product_snapshot(instance),
        )
        return instance


def deactivate_product(
    *,
    company,
    actor,
    product: InsuranceProduct,
    request=None,
) -> InsuranceProduct:
    with transaction.atomic():
        if product.company_id != company.id:
            raise ValueError("Cross-tenant product deactivation blocked.")

        before = _product_snapshot(product)
        product.status = InsuranceProduct.Status.INACTIVE
        product.save(update_fields=("status", "updated_at"))
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.product.deactivate",
            resource_label="insurance_core.InsuranceProduct",
            resource_pk=str(product.pk),
            request=request,
            data_before=before,
            data_after=_product_snapshot(product),
        )
        return product


def upsert_coverage(
    *,
    company,
    actor,
    instance: ProductCoverage | None,
    data: dict,
    request=None,
) -> ProductCoverage:
    with transaction.atomic():
        if instance is None:
            coverage = ProductCoverage(company=company, **data)
            coverage.save()
            publish_tenant_event(
                company=company,
                actor=actor,
                action=LedgerEntry.ACTION_CREATE,
                event_type="insurance_core.coverage.create",
                resource_label="insurance_core.ProductCoverage",
                resource_pk=str(coverage.pk),
                request=request,
                data_after=_coverage_snapshot(coverage),
            )
            return coverage

        if instance.company_id != company.id:
            raise ValueError("Cross-tenant coverage update blocked.")

        before = _coverage_snapshot(instance)
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_UPDATE,
            event_type="insurance_core.coverage.update",
            resource_label="insurance_core.ProductCoverage",
            resource_pk=str(instance.pk),
            request=request,
            data_before=before,
            data_after=_coverage_snapshot(instance),
        )
        return instance


def delete_coverage(
    *,
    company,
    actor,
    coverage: ProductCoverage,
    request=None,
) -> None:
    with transaction.atomic():
        if coverage.company_id != company.id:
            raise ValueError("Cross-tenant coverage deletion blocked.")

        before = _coverage_snapshot(coverage)
        pk = coverage.pk
        coverage.delete()
        publish_tenant_event(
            company=company,
            actor=actor,
            action=LedgerEntry.ACTION_DELETE,
            event_type="insurance_core.coverage.delete",
            resource_label="insurance_core.ProductCoverage",
            resource_pk=str(pk),
            request=request,
            data_before=before,
            data_after=None,
        )

