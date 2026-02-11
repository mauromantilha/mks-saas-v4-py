from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from control_plane.models import Plan, PlanPrice, Tenant, TenantPlanSubscription
from customers.models import Company


@dataclass(frozen=True)
class DefaultPlanSpec:
    name: str
    tier: str
    monthly_price: Decimal
    setup_fee: Decimal


DEFAULT_PLAN_SPECS: tuple[DefaultPlanSpec, ...] = (
    DefaultPlanSpec(
        name="Básico",
        tier=Plan.TIER_STARTER,
        monthly_price=Decimal("150.00"),
        setup_fee=Decimal("150.00"),
    ),
    DefaultPlanSpec(
        name="Intermediário",
        tier=Plan.TIER_GROWTH,
        monthly_price=Decimal("250.00"),
        setup_fee=Decimal("150.00"),
    ),
    DefaultPlanSpec(
        name="Premium",
        tier=Plan.TIER_ENTERPRISE,
        monthly_price=Decimal("350.00"),
        setup_fee=Decimal("150.00"),
    ),
)


def ensure_default_plans() -> dict[str, Plan]:
    """
    Ensure base commercial plans always exist in Control Panel.

    Returns a mapping by plan tier.
    """

    plans_by_tier: dict[str, Plan] = {}

    with transaction.atomic():
        for spec in DEFAULT_PLAN_SPECS:
            plan = Plan.objects.filter(name=spec.name).order_by("-is_active", "id").first()
            if plan is None:
                plan = (
                    Plan.objects.filter(tier=spec.tier)
                    .order_by("-is_active", "id")
                    .first()
                )
            if plan is None:
                plan = Plan.objects.create(
                    name=spec.name,
                    tier=spec.tier,
                    is_active=True,
                )
            else:
                changed_fields: list[str] = []
                if plan.name != spec.name and not Plan.objects.filter(name=spec.name).exclude(pk=plan.pk).exists():
                    plan.name = spec.name
                    changed_fields.append("name")
                if plan.tier != spec.tier:
                    plan.tier = spec.tier
                    changed_fields.append("tier")
                if not plan.is_active:
                    plan.is_active = True
                    changed_fields.append("is_active")
                if changed_fields:
                    plan.save(update_fields=[*changed_fields, "updated_at"])

            price, _created = PlanPrice.objects.get_or_create(
                plan=plan,
                defaults={
                    "monthly_price": spec.monthly_price,
                    "setup_fee": spec.setup_fee,
                },
            )
            price_changed_fields: list[str] = []
            if price.monthly_price != spec.monthly_price:
                price.monthly_price = spec.monthly_price
                price_changed_fields.append("monthly_price")
            if price.setup_fee != spec.setup_fee:
                price.setup_fee = spec.setup_fee
                price_changed_fields.append("setup_fee")
            if price_changed_fields:
                price.full_clean()
                price.save(update_fields=[*price_changed_fields, "updated_at"])

            plans_by_tier[spec.tier] = plan

    return plans_by_tier


def backfill_tenants_from_companies(starter_plan: Plan) -> int:
    """
    Backfill control-plane Tenant rows for legacy Company rows.

    Returns the number of created Tenant records.
    """

    created_count = 0
    companies = (
        Company.objects.select_related("control_tenant")
        .all()
    )

    with transaction.atomic():
        for company in companies:
            if hasattr(company, "control_tenant"):
                continue

            tenant = Tenant.objects.create(
                company=company,
                legal_name=company.name,
                cnpj="",
                contact_email="",
                slug=company.tenant_code,
                subdomain=company.subdomain,
                status=Tenant.STATUS_ACTIVE if company.is_active else Tenant.STATUS_SUSPENDED,
                cep="",
                street="",
                number="",
                complement="",
                district="",
                city="",
                state="",
            )
            TenantPlanSubscription.objects.create(
                tenant=tenant,
                plan=starter_plan,
                is_trial=False,
                trial_ends_at=None,
                is_courtesy=False,
                setup_fee_override=None,
                status=TenantPlanSubscription.STATUS_ACTIVE,
            )
            created_count += 1

    return created_count


def ensure_control_panel_baseline_data() -> None:
    """
    Ensure Control Panel can always render with baseline business catalog.

    - Seeds default plans (Básico/Intermediário/Premium)
    - Backfills Tenant rows for existing Company records (e.g. legacy Acme)
    """

    plans_by_tier = ensure_default_plans()
    starter_plan = plans_by_tier[Plan.TIER_STARTER]
    backfill_tenants_from_companies(starter_plan)

    tenants_without_active_subscription = (
        Tenant.objects.exclude(subscriptions__status=TenantPlanSubscription.STATUS_ACTIVE)
        .distinct()
    )
    for tenant in tenants_without_active_subscription:
        TenantPlanSubscription.objects.create(
            tenant=tenant,
            plan=starter_plan,
            is_trial=False,
            trial_ends_at=None,
            is_courtesy=False,
            setup_fee_override=None,
            status=TenantPlanSubscription.STATUS_ACTIVE,
        )
