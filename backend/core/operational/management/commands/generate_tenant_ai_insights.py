from django.conf import settings
from django.core.management.base import BaseCommand

from customers.models import Company
from operational.views import _compute_dashboard_ai_insights, _save_dashboard_ai_interaction


class Command(BaseCommand):
    help = "Generate automatic dashboard AI insights for active tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=("daily", "weekly"),
            default="daily",
            help="daily=30d executive insight, weekly=7d action plan.",
        )
        parser.add_argument(
            "--tenant",
            dest="tenant_code",
            default="",
            help="Optional tenant_code to run a single tenant.",
        )

    def handle(self, *args, **options):
        mode = options["mode"]
        tenant_code = (options.get("tenant_code") or "").strip().lower()
        weekly_plan = mode == "weekly"
        period_days = 7 if weekly_plan else 30
        focus = (
            "Plano semanal com prioridades de vendas, inadimplência e eficiência operacional."
            if weekly_plan
            else "Resumo executivo de performance comercial e financeira."
        )

        tenants = Company.objects.filter(is_active=True).order_by("id")
        if tenant_code:
            tenants = tenants.filter(tenant_code=tenant_code)

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No active tenant found for the selected filter."))
            return

        use_django_tenants = bool(getattr(settings, "DJANGO_TENANTS_ENABLED", False))
        if use_django_tenants:
            from django_tenants.utils import schema_context

        generated = 0
        failed = 0
        for company in tenants.iterator():
            try:
                if use_django_tenants:
                    with schema_context(company.schema_name):
                        context, insights = _compute_dashboard_ai_insights(
                            company,
                            period_days=period_days,
                            focus=focus,
                            weekly_plan=weekly_plan,
                        )
                        _save_dashboard_ai_interaction(
                            company=company,
                            actor=None,
                            period_days=period_days,
                            weekly_plan=weekly_plan,
                            focus=focus,
                            context=context,
                            insights=insights,
                            is_auto=True,
                        )
                else:
                    context, insights = _compute_dashboard_ai_insights(
                        company,
                        period_days=period_days,
                        focus=focus,
                        weekly_plan=weekly_plan,
                    )
                    _save_dashboard_ai_interaction(
                        company=company,
                        actor=None,
                        period_days=period_days,
                        weekly_plan=weekly_plan,
                        focus=focus,
                        context=context,
                        insights=insights,
                        is_auto=True,
                    )
                generated += 1
                self.stdout.write(self.style.SUCCESS(f"[ok] tenant={company.tenant_code}"))
            except Exception as exc:  # pragma: no cover
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f"[fail] tenant={company.tenant_code} error={exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed mode={mode}. generated={generated} failed={failed}"
            )
        )
