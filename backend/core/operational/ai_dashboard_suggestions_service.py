from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.db.models import Q, Sum

from finance.models import Payable, ReceivableInstallment
from operational.ai_assistant_service import CapabilityGate
from operational.ai_assistant_selectors import build_system_health_snapshot
from operational.models import AiSuggestion, Apolice, Customer, Lead


@dataclass
class DashboardSuggestionsService:
    company: Any
    user: Any
    cache_hours: int = 6

    @classmethod
    def build(cls, *, company, user, cache_hours: int = 6) -> "DashboardSuggestionsService":
        safe_cache = max(1, min(48, int(cache_hours)))
        return cls(company=company, user=user, cache_hours=safe_cache)

    def _window(self) -> tuple[timezone.datetime, timezone.datetime]:
        now = timezone.now()
        return now, now - timedelta(hours=self.cache_hours)

    def _active_queryset(self):
        now, _ = self._window()
        return AiSuggestion.all_objects.filter(
            company=self.company,
            scope=AiSuggestion.Scope.DASHBOARD,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    def _latest_queryset(self):
        return AiSuggestion.all_objects.filter(
            company=self.company,
            scope=AiSuggestion.Scope.DASHBOARD,
        ).order_by("-created_at", "-id")

    def list_or_generate(self) -> tuple[list[AiSuggestion], dict[str, Any]]:
        now, threshold = self._window()
        active = list(self._active_queryset().order_by("-created_at", "-id"))
        if active:
            return active, {"cached": True, "generated": False, "stale": False}

        latest = self._latest_queryset()
        latest_row = latest.first()
        if latest_row and latest_row.created_at >= threshold:
            return list(latest[:8]), {"cached": True, "generated": False, "stale": True}

        created = self._generate(now=now)
        return created, {"cached": False, "generated": True, "stale": False}

    def _generate(self, *, now):
        expires_at = now + timedelta(hours=self.cache_hours)
        gate = CapabilityGate.build(self.company, self.user)
        ai_caps = gate.ai_capabilities()

        suggestions_to_create: list[AiSuggestion] = []

        health = build_system_health_snapshot(self.company)
        if health.get("available"):
            status = str(health.get("status") or "unknown")
            summary = health.get("summary") or {}
            severity = "HIGH" if status != "healthy" else "LOW"
            suggestions_to_create.append(
                AiSuggestion(
                    company=self.company,
                    scope=AiSuggestion.Scope.DASHBOARD,
                    title="Saúde do sistema do tenant",
                    body=(
                        f"Status: {status}. "
                        f"Erro: {summary.get('error_rate', 0):.2%}, "
                        f"latência p95: {summary.get('p95_latency', 0):.0f}ms, "
                        f"jobs pendentes: {summary.get('jobs_pending', 0)}."
                    ),
                    severity=severity,
                    priority="HIGH" if status != "healthy" else "LOW",
                    related_entity_type="tenant_health",
                    related_entity_id="",
                    expires_at=expires_at,
                )
            )

        top_leads = list(
            Lead.all_objects.filter(
                company=self.company,
                status__in=("NEW", "QUALIFIED"),
            )
            .order_by("-qualification_score", "-created_at")
            .values("id", "company_name", "full_name", "qualification_score")[:5]
        )
        if top_leads:
            lead_labels = [
                row.get("company_name")
                or row.get("full_name")
                or f"Lead #{row.get('id')}"
                for row in top_leads
            ]
            suggestions_to_create.append(
                AiSuggestion(
                    company=self.company,
                    scope=AiSuggestion.Scope.DASHBOARD,
                    title="Leads prioritários sem fechamento",
                    body="Top leads pendentes: " + ", ".join(lead_labels[:3]) + ".",
                    severity="MEDIUM",
                    priority="MEDIUM",
                    related_entity_type="lead",
                    related_entity_id=str(top_leads[0]["id"]),
                    expires_at=expires_at,
                )
            )

        potential_customers = list(
            Customer.all_objects.filter(company=self.company)
            .annotate(
                pipeline_value=Sum(
                    "opportunities__amount",
                    filter=~Q(opportunities__stage__in=("WON", "LOST")),
                )
            )
            .order_by("-pipeline_value", "name")
            .values("id", "name", "pipeline_value")[:5]
        )
        if potential_customers:
            top = potential_customers[0]
            suggestions_to_create.append(
                AiSuggestion(
                    company=self.company,
                    scope=AiSuggestion.Scope.DASHBOARD,
                    title="Cliente com maior potencial de pipeline",
                    body=(
                        f"Cliente destaque: {top.get('name')} "
                        f"(pipeline estimado R$ {float(top.get('pipeline_value') or 0):.2f})."
                    ),
                    severity="LOW",
                    priority="MEDIUM",
                    related_entity_type="customer",
                    related_entity_id=str(top["id"]),
                    expires_at=expires_at,
                )
            )

        if ai_caps.get("tenant.ai.finance", False):
            today = timezone.localdate()
            overdue = ReceivableInstallment.all_objects.filter(
                company=self.company,
                status=ReceivableInstallment.STATUS_OPEN,
                due_date__lt=today,
            ).aggregate(total=Sum("amount"))
            upcoming_payables = Payable.all_objects.filter(
                company=self.company,
                status=Payable.STATUS_OPEN,
                due_date__gte=today,
                due_date__lte=today + timedelta(days=7),
            ).aggregate(total=Sum("amount"))
            overdue_total = float(overdue.get("total") or 0)
            payables_total = float(upcoming_payables.get("total") or 0)
            if overdue_total > 0 or payables_total > 0:
                suggestions_to_create.append(
                    AiSuggestion(
                        company=self.company,
                        scope=AiSuggestion.Scope.DASHBOARD,
                        title="Atenção financeira imediata",
                        body=(
                            f"Parcelas atrasadas: R$ {overdue_total:.2f}. "
                            f"Payables próximos (7 dias): R$ {payables_total:.2f}."
                        ),
                        severity="HIGH" if overdue_total > 0 else "MEDIUM",
                        priority="HIGH" if overdue_total > 0 else "MEDIUM",
                        related_entity_type="finance",
                        related_entity_id="",
                        expires_at=expires_at,
                    )
                )

        renewal_limit = timezone.localdate() + timedelta(days=30)
        renewing = Apolice.all_objects.filter(
            company=self.company,
            status="ATIVA",
            fim_vigencia__lte=renewal_limit,
        ).count()
        cancelled = Apolice.all_objects.filter(
            company=self.company,
            status="CANCELADA",
        ).count()
        if renewing or cancelled:
            suggestions_to_create.append(
                AiSuggestion(
                    company=self.company,
                    scope=AiSuggestion.Scope.DASHBOARD,
                    title="Carteira de apólices: renovação/cancelamento",
                    body=(
                        f"Apólices para renovar em 30 dias: {renewing}. "
                        f"Apólices canceladas na base: {cancelled}."
                    ),
                    severity="MEDIUM" if renewing else "LOW",
                    priority="MEDIUM",
                    related_entity_type="apolice",
                    related_entity_id="",
                    expires_at=expires_at,
                )
            )

        if not suggestions_to_create:
            suggestions_to_create.append(
                AiSuggestion(
                    company=self.company,
                    scope=AiSuggestion.Scope.DASHBOARD,
                    title="Sem alertas críticos no momento",
                    body="Nenhum indicador prioritário identificado para ação imediata.",
                    severity="LOW",
                    priority="LOW",
                    related_entity_type="dashboard",
                    related_entity_id="",
                    expires_at=expires_at,
                )
            )

        created = AiSuggestion.all_objects.bulk_create(suggestions_to_create)
        return sorted(created, key=lambda row: row.created_at, reverse=True)
