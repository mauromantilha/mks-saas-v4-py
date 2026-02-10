from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence

from django.db.models import Q
from django.utils import timezone

from commission.models import CommissionPlan, CommissionPlanScope, CommissionSplit


_HUNDRED = Decimal("100")
_CENT = Decimal("0.01")


class CommissionEngineError(RuntimeError):
    """Base error for commission engine failures."""


class CommissionRuleError(CommissionEngineError):
    """Raised when commission rules are invalid."""


class CommissionSplitError(CommissionEngineError):
    """Raised when split configuration is invalid."""


@dataclass(frozen=True, slots=True)
class CommissionResolution:
    plan: CommissionPlan
    scope: CommissionPlanScope | None
    rules_json: dict[str, Any]
    splits: list[CommissionSplit]


@dataclass(frozen=True, slots=True)
class SplitAllocation:
    participant: Any
    percentage: Decimal
    amount: Decimal


def _as_date(value: Any) -> date:
    if value is None:
        return timezone.localdate()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raise CommissionRuleError("Invalid date value.")


def _to_decimal(value: Any, *, field: str) -> Decimal:
    try:
        if isinstance(value, Decimal):
            return value
        if value is None or value == "":
            raise CommissionRuleError(f"Missing {field}.")
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise CommissionRuleError(f"Invalid decimal for {field}.") from exc


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _shallow_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, val in (override or {}).items():
        merged[key] = val
    return merged


def _read_context_ids(rules_json: Mapping[str, Any]) -> tuple[str, str]:
    context = rules_json.get("context") or rules_json.get("_context") or {}
    if not isinstance(context, Mapping):
        context = {}
    insurer_id = str(context.get("insurer_id") or rules_json.get("insurer_id") or "").strip()
    product_id = str(context.get("product_id") or rules_json.get("product_id") or "").strip()
    return insurer_id, product_id


def _apply_exceptions(rules_json: Mapping[str, Any]) -> dict[str, Any]:
    """Apply insurer/product exceptions onto the base rules.

    Expected structure:
    {
      "rate_pct": 10,
      "tiers": [...],
      "exceptions": {
        "insurer": {"<insurer_id>": {"rate_pct": 8}},
        "product": {"<product_id>": {"tiers": [...]}},
      }
    }

    Exception precedence (most specific last):
    - insurer override, then product override
    """

    base = dict(rules_json or {})
    exceptions = base.get("exceptions")
    if not isinstance(exceptions, Mapping):
        return base

    insurer_id, product_id = _read_context_ids(base)
    resolved = dict(base)

    insurer_overrides = exceptions.get("insurer") or exceptions.get("insurers") or {}
    if insurer_id and isinstance(insurer_overrides, Mapping):
        override = insurer_overrides.get(str(insurer_id))
        if isinstance(override, Mapping):
            resolved = _shallow_merge(resolved, override)

    product_overrides = exceptions.get("product") or exceptions.get("products") or {}
    if product_id and isinstance(product_overrides, Mapping):
        override = product_overrides.get(str(product_id))
        if isinstance(override, Mapping):
            resolved = _shallow_merge(resolved, override)

    return resolved


def _pick_tier(base_amount: Decimal, tiers: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    normalized: list[tuple[Decimal | None, Mapping[str, Any]]] = []
    for entry in tiers:
        if not isinstance(entry, Mapping):
            continue
        up_to = entry.get("up_to")
        if up_to is None or up_to == "":
            normalized.append((None, entry))
            continue
        normalized.append((_to_decimal(up_to, field="tiers.up_to"), entry))

    # Sort tiers with explicit ceilings first.
    normalized.sort(key=lambda item: (_HUNDRED if item[0] is None else item[0]))

    for ceiling, entry in normalized:
        if ceiling is None:
            # Fallback tier without ceiling.
            return entry
        if base_amount <= ceiling:
            return entry

    # No tier matched, return last (or empty dict).
    return normalized[-1][1] if normalized else {}


def calculate_commission(base_amount: Any, rules_json: Mapping[str, Any]) -> Decimal:
    """Calculate total commission from a base amount using rules_json.

    Supported:
    - Fixed rate: {"rate_pct": 10}
    - Tiers: {"tiers":[{"up_to":1000,"rate_pct":10},{"up_to":5000,"rate_pct":12},{"rate_pct":15}]}
    - Exceptions by insurer/product (see `_apply_exceptions`)
    """

    amount = _to_decimal(base_amount, field="base_amount")
    if amount < 0:
        raise CommissionRuleError("base_amount must be >= 0.")

    if not isinstance(rules_json, Mapping):
        raise CommissionRuleError("rules_json must be a mapping.")

    rules = _apply_exceptions(rules_json)

    rate_raw = rules.get("rate_pct", rules.get("fixed_rate_pct"))
    tiers = rules.get("tiers")

    if rate_raw is not None and rate_raw != "":
        rate_pct = _to_decimal(rate_raw, field="rate_pct")
        commission = amount * (rate_pct / _HUNDRED)
        return _round_money(commission)

    if isinstance(tiers, Sequence):
        tier = _pick_tier(amount, tiers)
        tier_rate_raw = tier.get("rate_pct", tier.get("fixed_rate_pct"))
        if tier_rate_raw is None or tier_rate_raw == "":
            return Decimal("0.00")
        tier_rate_pct = _to_decimal(tier_rate_raw, field="tier.rate_pct")
        commission = amount * (tier_rate_pct / _HUNDRED)
        return _round_money(commission)

    return Decimal("0.00")


def _participant_percentage(participant: Any) -> Decimal:
    if isinstance(participant, Mapping):
        value = participant.get("percentage", participant.get("pct"))
        return _to_decimal(value, field="percentage")
    if hasattr(participant, "percentage"):
        return _to_decimal(getattr(participant, "percentage"), field="percentage")
    raise CommissionSplitError("Split participant missing percentage.")


def apply_split(total_commission: Any, split_participants: Iterable[Any]) -> list[SplitAllocation]:
    """Apply a split over the total commission.

    Validation:
    - participants must sum to 100%
    - each participant percentage in [0, 100]

    Rounding:
    - amounts are rounded to cents
    - last participant receives the remainder to guarantee sum(total)=total_commission
    """

    total = _round_money(_to_decimal(total_commission, field="total_commission"))
    participants = list(split_participants or [])
    if not participants:
        raise CommissionSplitError("split_participants is required.")

    percentages = [_participant_percentage(p) for p in participants]
    for pct in percentages:
        if pct < 0 or pct > _HUNDRED:
            raise CommissionSplitError("Split percentages must be between 0 and 100.")

    pct_sum = sum(percentages, Decimal("0"))
    if pct_sum.quantize(Decimal("0.01")) != Decimal("100.00"):
        raise CommissionSplitError("Split percentages must sum to 100%.")

    allocations: list[SplitAllocation] = []
    allocated_total = Decimal("0.00")

    for idx, (participant, pct) in enumerate(zip(participants, percentages, strict=True)):
        if idx == len(participants) - 1:
            amount = total - allocated_total
        else:
            amount = _round_money(total * (pct / _HUNDRED))
            allocated_total += amount
        allocations.append(SplitAllocation(participant=participant, percentage=pct, amount=amount))

    return allocations


def _scope_rank(dimension: str) -> int:
    # Lower is more specific / preferred.
    ranks = {
        CommissionPlanScope.Dimension.PRODUCT: 10,
        CommissionPlanScope.Dimension.INSURER: 20,
        CommissionPlanScope.Dimension.LINE_OF_BUSINESS: 30,
        CommissionPlanScope.Dimension.SALES_CHANNEL: 40,
        CommissionPlanScope.Dimension.CUSTOM: 50,
        CommissionPlanScope.Dimension.ANY: 100,
    }
    return ranks.get(dimension, 999)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _extract(obj: Any, key: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, Mapping):
        return _safe_str(obj.get(key))
    return _safe_str(getattr(obj, key, ""))


def _scope_matches(
    scope: CommissionPlanScope,
    *,
    insurer_id: str,
    insurer_name: str,
    product_id: str,
    line_of_business: str,
    sales_channel: str,
) -> bool:
    value = (scope.value or "").strip()
    # Empty value means wildcard for the chosen dimension.
    if scope.dimension == CommissionPlanScope.Dimension.ANY:
        return True

    if scope.dimension == CommissionPlanScope.Dimension.INSURER:
        return (not value) or value == insurer_id or value.lower() == insurer_name.lower()

    if scope.dimension == CommissionPlanScope.Dimension.PRODUCT:
        return (not value) or value == product_id

    if scope.dimension == CommissionPlanScope.Dimension.LINE_OF_BUSINESS:
        return (not value) or value.lower() == line_of_business.lower()

    if scope.dimension == CommissionPlanScope.Dimension.SALES_CHANNEL:
        return (not value) or value.lower() == sales_channel.lower()

    if scope.dimension == CommissionPlanScope.Dimension.CUSTOM:
        # Minimal implementation: treat "value" as an opaque tag to be matched by sales_channel.
        # Future: add structured matchers here.
        return (not value) or value.lower() == sales_channel.lower()

    return False


def resolve_commission_plan(
    policy: Any,
    producer: Any,
    insurer: Any,
    product: Any,
    as_of: Any,
) -> CommissionResolution | None:
    """Resolve the best commission plan/scope for a given policy context.

    This function is tenant-safe: it always filters by `company` explicitly.
    """

    company = getattr(policy, "company", None)
    if company is None:
        raise CommissionRuleError("policy.company is required for commission resolution.")

    as_of_date = _as_date(as_of)

    resolved_insurer = insurer or getattr(policy, "insurer", None)
    resolved_product = product or getattr(policy, "product", None)

    insurer_id = _safe_str(getattr(resolved_insurer, "id", "") or getattr(policy, "insurer_id", ""))
    insurer_name = _extract(resolved_insurer, "name")
    product_id = _safe_str(getattr(resolved_product, "id", "") or getattr(policy, "product_id", ""))
    line_of_business = _extract(resolved_product, "line_of_business")
    sales_channel = _extract(producer, "sales_channel") or _extract(producer, "channel")

    active_plans = (
        CommissionPlan.all_objects.filter(company=company, status=CommissionPlan.Status.ACTIVE)
        .filter(effective_from__lte=as_of_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date))
        .order_by("priority", "id")
    )

    best_key: tuple[int, int, int, int] | None = None
    best_plan: CommissionPlan | None = None
    best_scope: CommissionPlanScope | None = None

    for plan in active_plans:
        scopes_qs = (
            CommissionPlanScope.all_objects.filter(company=company, plan=plan)
            .filter(effective_from__lte=as_of_date)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date))
        )
        matched_scopes = [
            scope
            for scope in scopes_qs
            if _scope_matches(
                scope,
                insurer_id=insurer_id,
                insurer_name=insurer_name,
                product_id=product_id,
                line_of_business=line_of_business,
                sales_channel=sales_channel,
            )
        ]

        if matched_scopes:
            matched_scopes.sort(
                key=lambda s: (_scope_rank(s.dimension), int(s.priority or 0), int(s.id or 0))
            )
            scope = matched_scopes[0]
            scope_key = (_scope_rank(scope.dimension), int(scope.priority or 0), int(scope.id or 0))
        else:
            scope = None
            scope_key = (999, 999, 999)

        key = (int(plan.priority or 0), *scope_key)
        if best_key is None or key < best_key:
            best_key = key
            best_plan = plan
            best_scope = scope

    if best_plan is None:
        return None

    base_rules: Mapping[str, Any] = best_plan.rules_json or {}
    override_rules: Mapping[str, Any] = best_scope.rules_json if best_scope is not None else {}
    merged_rules = _shallow_merge(base_rules, override_rules)
    merged_rules["context"] = _shallow_merge(
        merged_rules.get("context") if isinstance(merged_rules.get("context"), Mapping) else {},
        {
            "company_id": getattr(company, "id", None),
            "insurer_id": insurer_id or None,
            "product_id": product_id or None,
            "line_of_business": line_of_business or None,
        },
    )

    splits: list[CommissionSplit] = []
    if best_scope is not None:
        splits = list(
            CommissionSplit.all_objects.filter(company=company, scope=best_scope)
            .filter(effective_from__lte=as_of_date)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date))
            .order_by("priority", "id")
        )

    return CommissionResolution(plan=best_plan, scope=best_scope, rules_json=merged_rules, splits=splits)

