from __future__ import annotations

import re
from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import connection
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from control_plane.models import TenantAlertEvent, TenantHealthSnapshot
from finance.fiscal.models import FiscalDocument
from finance.models import Payable, ReceivableInstallment, ReceivableInvoice
from insurance_core.models import Insurer, Policy as InsurancePolicy
from operational.models import (
    AiDocumentChunk,
    Apolice,
    CommercialActivity,
    Customer,
    Lead,
    Opportunity,
)


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _metric(key: str, value: Any, *, source: str, period: str = "current") -> dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "source": source,
        "period": period,
    }


def build_internal_analytics_snapshot(
    company,
    *,
    include_financial_context: bool = True,
    include_commercial_context: bool = True,
) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []

    summary: dict[str, Any] = {
        "commercial": {},
        "financial": {},
        "insurance": {},
    }

    if include_commercial_context:
        leads = Lead.all_objects.filter(company=company).aggregate(
            total=Count("id"),
            hot=Count("id", filter=Q(lead_score_label=Lead.SCORE_HOT)),
            warm=Count("id", filter=Q(lead_score_label=Lead.SCORE_WARM)),
            cold=Count("id", filter=Q(lead_score_label=Lead.SCORE_COLD)),
            converted=Count("id", filter=Q(status="CONVERTED")),
        )
        opportunities = Opportunity.all_objects.filter(company=company).aggregate(
            total=Count("id"),
            won=Count("id", filter=Q(stage="WON")),
            lost=Count("id", filter=Q(stage="LOST")),
            pipeline_value=Sum("amount", filter=~Q(stage__in=("WON", "LOST"))),
        )
        activities = CommercialActivity.all_objects.filter(company=company).aggregate(
            open_total=Count("id", filter=Q(status=CommercialActivity.STATUS_PENDING)),
            overdue_total=Count(
                "id",
                filter=Q(
                    status=CommercialActivity.STATUS_PENDING,
                    due_at__lt=timezone.now(),
                ),
            ),
            sla_breached=Count(
                "id",
                filter=Q(
                    status=CommercialActivity.STATUS_PENDING,
                    sla_due_at__isnull=False,
                    sla_due_at__lt=timezone.now(),
                ),
            ),
        )
        customers_total = Customer.all_objects.filter(company=company).count()

        summary["commercial"] = {
            "customers_total": customers_total,
            "leads": leads,
            "opportunities": {
                "total": opportunities.get("total", 0),
                "won": opportunities.get("won", 0),
                "lost": opportunities.get("lost", 0),
                "pipeline_value": _safe_float(opportunities.get("pipeline_value")),
            },
            "activities": activities,
        }

        metrics.extend(
            [
                _metric(
                    "customers.total",
                    customers_total,
                    source="operational.customers",
                ),
                _metric(
                    "leads.total",
                    leads.get("total", 0),
                    source="operational.leads",
                ),
                _metric(
                    "leads.hot",
                    leads.get("hot", 0),
                    source="operational.leads",
                ),
                _metric(
                    "opportunities.pipeline_value",
                    _safe_float(opportunities.get("pipeline_value")),
                    source="operational.opportunities",
                ),
                _metric(
                    "activities.overdue_total",
                    activities.get("overdue_total", 0),
                    source="operational.activities",
                ),
            ]
        )
        datasets.extend(
            [
                {
                    "name": "operational.leads",
                    "ids": list(
                        Lead.all_objects.filter(company=company)
                        .order_by("-created_at")
                        .values_list("id", flat=True)[:8]
                    ),
                },
                {
                    "name": "operational.opportunities",
                    "ids": list(
                        Opportunity.all_objects.filter(company=company)
                        .order_by("-created_at")
                        .values_list("id", flat=True)[:8]
                    ),
                },
            ]
        )

    insurance_summary = {
        "legacy_apolices_active": Apolice.all_objects.filter(company=company, status="ATIVA").count(),
        "core_policies_active": InsurancePolicy.all_objects.filter(
            company=company,
            status=InsurancePolicy.Status.ACTIVE,
        ).count(),
        "insurers_total": Insurer.all_objects.filter(company=company).count(),
    }
    summary["insurance"] = insurance_summary
    metrics.extend(
        [
            _metric(
                "insurance.apolices_active",
                insurance_summary["legacy_apolices_active"],
                source="operational.apolices",
            ),
            _metric(
                "insurance.policies_active",
                insurance_summary["core_policies_active"],
                source="insurance_core.policies",
            ),
            _metric(
                "insurance.insurers_total",
                insurance_summary["insurers_total"],
                source="insurance_core.insurers",
            ),
        ]
    )

    if include_financial_context:
        today = timezone.localdate()
        receivables_open = ReceivableInstallment.all_objects.filter(
            company=company,
            status=ReceivableInstallment.STATUS_OPEN,
        )
        receivables_paid = ReceivableInstallment.all_objects.filter(
            company=company,
            status=ReceivableInstallment.STATUS_PAID,
        )
        payables_open = Payable.all_objects.filter(company=company, status=Payable.STATUS_OPEN)
        payables_paid = Payable.all_objects.filter(company=company, status=Payable.STATUS_PAID)
        invoices_open = ReceivableInvoice.all_objects.filter(
            company=company,
            status=ReceivableInvoice.STATUS_OPEN,
        )
        fiscal_open = FiscalDocument.all_objects.filter(
            company=company,
            status__in=(
                FiscalDocument.Status.DRAFT,
                FiscalDocument.Status.EMITTING,
            ),
        )

        summary["financial"] = {
            "receivables_open_total": _safe_float(receivables_open.aggregate(total=Sum("amount"))["total"]),
            "receivables_paid_total": _safe_float(receivables_paid.aggregate(total=Sum("amount"))["total"]),
            "payables_open_total": _safe_float(payables_open.aggregate(total=Sum("amount"))["total"]),
            "payables_paid_total": _safe_float(payables_paid.aggregate(total=Sum("amount"))["total"]),
            "receivables_overdue_total": _safe_float(
                receivables_open.filter(due_date__lt=today).aggregate(total=Sum("amount"))["total"]
            ),
            "invoices_open_count": invoices_open.count(),
            "fiscal_pending_count": fiscal_open.count(),
        }

        metrics.extend(
            [
                _metric(
                    "finance.receivables_open_total",
                    summary["financial"]["receivables_open_total"],
                    source="finance.receivable_installments",
                ),
                _metric(
                    "finance.payables_open_total",
                    summary["financial"]["payables_open_total"],
                    source="finance.payables",
                ),
                _metric(
                    "finance.receivables_overdue_total",
                    summary["financial"]["receivables_overdue_total"],
                    source="finance.receivable_installments",
                ),
                _metric(
                    "finance.invoices_open_count",
                    summary["financial"]["invoices_open_count"],
                    source="finance.receivable_invoices",
                ),
                _metric(
                    "finance.fiscal_pending_count",
                    summary["financial"]["fiscal_pending_count"],
                    source="finance_fiscal.fiscal_documents",
                ),
            ]
        )
        datasets.append(
            {
                "name": "finance.receivable_invoices",
                "ids": list(
                    invoices_open.order_by("-issue_date", "-id").values_list("id", flat=True)[:8]
                ),
            }
        )

    return {
        "as_of": timezone.now().isoformat(),
        "summary": summary,
        "metrics": metrics,
        "datasets": datasets,
    }


def build_system_health_snapshot(company) -> dict[str, Any]:
    tenant = getattr(company, "control_tenant", None)
    if tenant is None:
        return {
            "available": False,
            "status": "unknown",
            "reason": "Tenant não possui vínculo com control_plane.Tenant.",
            "summary": {},
            "alerts": [],
            "recommendations": [],
        }

    latest = TenantHealthSnapshot.objects.filter(tenant=tenant).order_by("-captured_at").first()
    alerts = list(
        TenantAlertEvent.objects.filter(
            tenant=tenant,
            status=TenantAlertEvent.STATUS_OPEN,
        )
        .order_by("-last_seen_at")
        .values("id", "alert_type", "severity", "message", "last_seen_at")[:10]
    )

    if latest is None:
        return {
            "available": False,
            "status": "unknown",
            "reason": "Sem snapshots de saúde para o tenant.",
            "summary": {},
            "alerts": alerts,
            "recommendations": [],
        }

    summary = {
        "captured_at": latest.captured_at.isoformat(),
        "request_rate": float(latest.request_rate),
        "error_rate": float(latest.error_rate),
        "p95_latency": float(latest.p95_latency),
        "jobs_pending": int(latest.jobs_pending),
    }

    recommendations: list[str] = []
    status = "healthy"
    if summary["error_rate"] > 0.05:
        status = "warning"
        recommendations.append("Taxa de erro acima de 5%; revisar logs e últimas alterações.")
    if summary["p95_latency"] > 1500:
        status = "warning"
        recommendations.append("Latência p95 elevada; revisar gargalos de banco e integrações externas.")
    if summary["jobs_pending"] > 20:
        status = "warning"
        recommendations.append("Fila de jobs acumulada; avaliar workers e retentativas.")
    if alerts:
        status = "warning"
        recommendations.append("Existem alertas abertos no monitoramento do tenant.")

    return {
        "available": True,
        "status": status,
        "summary": summary,
        "alerts": alerts,
        "recommendations": recommendations,
    }


def search_ai_document_chunks(company, query: str, *, limit: int = 6):
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    limit = max(1, min(20, int(limit)))
    base_qs = AiDocumentChunk.all_objects.filter(company=company)

    if connection.vendor == "postgresql":
        search_query = SearchQuery(normalized_query, config="portuguese")
        ranked_qs = (
            base_qs.annotate(rank=SearchRank(F("search_vector"), search_query))
            .filter(search_vector=search_query)
            .order_by("-rank", "document_name", "chunk_order", "id")
        )
        ranked_results = list(ranked_qs[:limit])
        if ranked_results:
            return ranked_results

    terms = [term for term in re.split(r"\s+", normalized_query) if len(term) >= 3][:8]
    text_filter = Q()
    for term in terms:
        text_filter |= Q(chunk_text__icontains=term)
        text_filter |= Q(document_name__icontains=term)

    if not terms:
        text_filter = Q(chunk_text__icontains=normalized_query)

    return list(base_qs.filter(text_filter).order_by("document_name", "chunk_order", "id")[:limit])
