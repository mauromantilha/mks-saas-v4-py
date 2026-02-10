from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from control_plane.models import (
    AdminAuditEvent,
    FeatureFlag,
    ContractEmailLog,
    ControlPanelAuditLog,
    Plan,
    PlanPrice,
    SystemHealthSnapshot,
    Tenant,
    TenantAlertEvent,
    TenantContractDocument,
    TenantFeatureFlag,
    TenantHealthSnapshot,
    TenantImpersonationSession,
    TenantIntegrationSecretRef,
    TenantInternalNote,
    TenantOperationalSettings,
    TenantPlanSubscription,
    TenantReleaseRecord,
    TenantStatusHistory,
)
from control_plane.permissions import IsControlPanelAdmin
from control_plane.serializers import (
    AdminAuditEventSerializer,
    ContractEmailLogSerializer,
    ContractSendSerializer,
    ControlPanelTenantCreateSerializer,
    ControlPanelTenantSerializer,
    ControlPanelTenantUpdateSerializer,
    FeatureFlagSerializer,
    PlanSerializer,
    PlanWriteSerializer,
    SystemHealthSnapshotSerializer,
    TenantContractDocumentSerializer,
    TenantFeatureFlagSerializer,
    TenantFeatureFlagWriteSerializer,
    TenantHealthSnapshotSerializer,
    TenantImpersonationSessionSerializer,
    TenantImpersonationStartSerializer,
    TenantImpersonationStopSerializer,
    TenantIntegrationSecretRefSerializer,
    TenantIntegrationSecretRefWriteSerializer,
    TenantOperationalSettingsSerializer,
    TenantOperationalSettingsWriteSerializer,
    TenantAlertEventSerializer,
    TenantAlertResolveSerializer,
    TenantReleaseRecordSerializer,
    TenantReleaseRecordWriteSerializer,
    TenantSoftDeleteActionSerializer,
    TenantInternalNoteSerializer,
    TenantInternalNoteWriteSerializer,
    TenantStatusActionSerializer,
    TenantSubscriptionChangeSerializer,
)
from control_plane.services.contracts import ContractServiceError, generate_contract, send_contract_email
from customers.models import Company


def _mask_cnpj(cnpj: str) -> str:
    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def _audit(actor, tenant: Tenant | None, action: str, metadata: dict) -> None:
    safe_metadata = dict(metadata)
    if "cnpj" in safe_metadata:
        safe_metadata["cnpj"] = _mask_cnpj(str(safe_metadata["cnpj"]))
    actor_ref = actor if getattr(actor, "is_authenticated", False) else None
    ControlPanelAuditLog.objects.create(
        actor=actor_ref,
        tenant=tenant,
        action=action,
        resource="tenant",
        metadata=safe_metadata,
    )
    entity_type = str(safe_metadata.get("resource", "tenant"))
    entity_id = safe_metadata.get("entity_id")
    if entity_id is None:
        entity_id = safe_metadata.get("tenant_id")
    if entity_id is None and tenant is not None:
        entity_id = tenant.id
    AdminAuditEvent.objects.create(
        actor=actor_ref,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else "",
        target_tenant=tenant,
        before_data=safe_metadata.get("before", {}),
        after_data=safe_metadata.get("after", safe_metadata),
        correlation_id=str(safe_metadata.get("correlation_id", ""))[:64],
    )


def _parse_monitoring_period(raw_period: str | None) -> tuple[str, timezone.datetime | None]:
    """
    Supported period values:
    - 1h, 6h, 24h, 7d, 30d
    """
    normalized = (raw_period or "").strip().lower()
    if not normalized:
        return ("all", None)

    mapping = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = mapping.get(normalized)
    if delta is None:
        return ("all", None)
    return (normalized, timezone.now() - delta)


def _mark_alert_open(
    tenant: Tenant,
    *,
    alert_type: str,
    severity: str,
    message: str,
    metrics_json: dict | None = None,
) -> TenantAlertEvent:
    now = timezone.now()
    alert, created = TenantAlertEvent.objects.get_or_create(
        tenant=tenant,
        alert_type=alert_type,
        status=TenantAlertEvent.STATUS_OPEN,
        defaults={
            "severity": severity,
            "message": message,
            "metrics_json": metrics_json or {},
        },
    )
    if not created:
        alert.severity = severity
        alert.message = message
        alert.metrics_json = metrics_json or {}
        alert.last_seen_at = now
        alert.save(update_fields=["severity", "message", "metrics_json", "last_seen_at"])
    return alert


def _resolve_open_alert(tenant: Tenant, alert_type: str) -> None:
    now = timezone.now()
    open_alert = (
        TenantAlertEvent.objects.filter(
            tenant=tenant,
            alert_type=alert_type,
            status=TenantAlertEvent.STATUS_OPEN,
        )
        .order_by("-last_seen_at")
        .first()
    )
    if open_alert is None:
        return
    open_alert.status = TenantAlertEvent.STATUS_RESOLVED
    open_alert.resolved_at = now
    open_alert.save(update_fields=["status", "resolved_at", "last_seen_at"])


class ControlPanelTenantViewSet(viewsets.ViewSet):
    permission_classes = [IsControlPanelAdmin]

    def get_queryset(self):
        return Tenant.objects.select_related("company").prefetch_related(
            "subscriptions__plan",
            "subscriptions__plan__price",
        )

    def list(self, request):
        queryset = self.get_queryset().order_by("legal_name")
        status_value = request.query_params.get("status", "").strip().upper()
        plan_value = request.query_params.get("plan", "").strip()
        trial_value = request.query_params.get("trial", "").strip().lower()
        search = request.query_params.get("search", "").strip()

        if status_value:
            queryset = queryset.filter(status=status_value)
        if plan_value:
            queryset = queryset.filter(subscriptions__plan_id=plan_value).distinct()
        if trial_value in {"true", "false"}:
            queryset = queryset.filter(subscriptions__is_trial=(trial_value == "true")).distinct()
        if search:
            queryset = queryset.filter(
                Q(legal_name__icontains=search) | Q(cnpj__icontains=search)
            )

        serializer = ControlPanelTenantSerializer(queryset, many=True)
        _audit(
            request.user,
            None,
            ControlPanelAuditLog.ACTION_LIST,
            {
                "filters": {
                    "status": status_value,
                    "plan": plan_value,
                    "trial": trial_value,
                    "search": bool(search),
                },
                "result_count": len(serializer.data),
            },
        )
        return Response(serializer.data)

    def create(self, request):
        serializer = ControlPanelTenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        subscription_payload = payload.pop("subscription", None)

        try:
            with transaction.atomic():
                company = Company.objects.create(
                    name=payload["legal_name"],
                    tenant_code=payload["slug"],
                    subdomain=payload["subdomain"],
                    is_active=payload.get("status", Tenant.STATUS_ACTIVE) == Tenant.STATUS_ACTIVE,
                )
                tenant = Tenant(company=company, **payload)
                tenant.full_clean()
                tenant.save()

                if subscription_payload:
                    subscription = TenantPlanSubscription(tenant=tenant, **subscription_payload)
                    subscription.full_clean()
                    subscription.save()

                _audit(
                    request.user,
                    tenant,
                    ControlPanelAuditLog.ACTION_CREATE,
                    {"tenant_id": tenant.id, "status": tenant.status, "cnpj": tenant.cnpj},
                )
        except IntegrityError:
            return Response(
                {"detail": "Tenant slug/subdomain already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ControlPanelTenantSerializer(tenant).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_RETRIEVE,
            {"tenant_id": tenant.id},
        )
        return Response(ControlPanelTenantSerializer(tenant).data)

    def partial_update(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = ControlPanelTenantUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        subscription_payload = payload.pop("subscription", None)
        target_status = payload.get("status")
        if (
            target_status == Tenant.STATUS_ACTIVE
            and tenant.status != Tenant.STATUS_ACTIVE
            and not request.user.is_superuser
        ):
            return Response(
                {"detail": "Only SUPERADMIN can reactivate a tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            with transaction.atomic():
                changed_fields = []
                for field, value in payload.items():
                    setattr(tenant, field, value)
                    changed_fields.append(field)

                if changed_fields:
                    tenant.full_clean()
                    tenant.save(update_fields=changed_fields + ["updated_at"])
                    tenant.company.name = tenant.legal_name
                    tenant.company.subdomain = tenant.subdomain
                    tenant.company.tenant_code = tenant.slug
                    tenant.company.is_active = tenant.status == Tenant.STATUS_ACTIVE
                    tenant.company.save(
                        update_fields=["name", "subdomain", "tenant_code", "is_active", "updated_at"]
                    )

                if subscription_payload:
                    sub = tenant.subscriptions.order_by("-created_at").first()
                    if sub is None:
                        sub = TenantPlanSubscription(tenant=tenant, **subscription_payload)
                    else:
                        for field, value in subscription_payload.items():
                            setattr(sub, field, value)
                    sub.full_clean()
                    sub.save()

                _audit(
                    request.user,
                    tenant,
                    ControlPanelAuditLog.ACTION_UPDATE,
                    {"tenant_id": tenant.id, "updated_fields": changed_fields, "cnpj": tenant.cnpj},
                )
        except IntegrityError:
            return Response(
                {"detail": "Tenant slug/subdomain already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        tenant.refresh_from_db()
        return Response(ControlPanelTenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = TenantStatusActionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            old_status = tenant.status
            if tenant.status != Tenant.STATUS_SUSPENDED:
                tenant.status = Tenant.STATUS_SUSPENDED
                tenant.save(update_fields=["status", "updated_at"])
                tenant.company.is_active = False
                tenant.company.save(update_fields=["is_active", "updated_at"])
                TenantStatusHistory.objects.create(
                    tenant=tenant,
                    from_status=old_status,
                    to_status=Tenant.STATUS_SUSPENDED,
                    reason=serializer.validated_data.get("reason", ""),
                    actor=request.user if request.user.is_authenticated else None,
                )
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_SUSPEND,
                {"tenant_id": tenant.id, "from_status": old_status, "to_status": Tenant.STATUS_SUSPENDED},
            )

        return Response(ControlPanelTenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="unsuspend")
    def unsuspend(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = TenantStatusActionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only SUPERADMIN can reactivate a tenant."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            if tenant.status == Tenant.STATUS_SUSPENDED:
                old_status = tenant.status
                tenant.status = Tenant.STATUS_ACTIVE
                tenant.save(update_fields=["status", "updated_at"])
                tenant.company.is_active = True
                tenant.company.save(update_fields=["is_active", "updated_at"])
                TenantStatusHistory.objects.create(
                    tenant=tenant,
                    from_status=old_status,
                    to_status=Tenant.STATUS_ACTIVE,
                    reason=serializer.validated_data.get("reason", ""),
                    actor=request.user if request.user.is_authenticated else None,
                )
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_UNSUSPEND,
                {"tenant_id": tenant.id, "to_status": Tenant.STATUS_ACTIVE},
            )

        return Response(ControlPanelTenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="delete")
    def soft_delete(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = TenantSoftDeleteActionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            old_status = tenant.status
            tenant.status = Tenant.STATUS_DELETED
            tenant.deleted_at = timezone.now()
            tenant.save(update_fields=["status", "deleted_at", "updated_at"])
            tenant.company.is_active = False
            tenant.company.save(update_fields=["is_active", "updated_at"])
            TenantStatusHistory.objects.create(
                tenant=tenant,
                from_status=old_status,
                to_status=Tenant.STATUS_DELETED,
                reason=serializer.validated_data.get("reason", ""),
                actor=request.user if request.user.is_authenticated else None,
            )
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_SOFT_DELETE,
                {
                    "tenant_id": tenant.id,
                    "from_status": old_status,
                    "to_status": Tenant.STATUS_DELETED,
                    "reason": serializer.validated_data.get("reason", ""),
                    "correlation_id": getattr(request, "correlation_id", ""),
                },
            )

        return Response(ControlPanelTenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], url_path="export")
    def export_data(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        subscription = tenant.subscriptions.select_related("plan", "plan__price").order_by("-created_at").first()
        notes = tenant.internal_notes.select_related("created_by").order_by("-created_at")[:200]
        features = tenant.feature_flags.select_related("feature").order_by("feature__name")

        payload = {
            "tenant": ControlPanelTenantSerializer(tenant).data,
            "subscription": {
                "plan": subscription.plan.name if subscription else None,
                "tier": subscription.plan.tier if subscription else None,
                "is_trial": subscription.is_trial if subscription else None,
                "trial_ends_at": subscription.trial_ends_at if subscription else None,
                "is_courtesy": subscription.is_courtesy if subscription else None,
                "setup_fee_override": str(subscription.setup_fee_override)
                if subscription and subscription.setup_fee_override is not None
                else None,
                "status": subscription.status if subscription else None,
            },
            "notes": [
                {
                    "id": note.id,
                    "note": note.note,
                    "created_by": note.created_by.username if note.created_by else None,
                    "created_at": note.created_at,
                }
                for note in notes
            ],
            "features": [
                {
                    "feature_key": row.feature.key,
                    "enabled": row.enabled,
                    "updated_at": row.updated_at,
                }
                for row in features
            ],
            "status_history": list(
                tenant.status_history.order_by("-created_at").values(
                    "from_status",
                    "to_status",
                    "reason",
                    "created_at",
                )[:200]
            ),
            "exported_at": timezone.now(),
        }
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_RETRIEVE,
            {
                "resource": "tenant_export",
                "tenant_id": tenant.id,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="subscription")
    def change_subscription(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = TenantSubscriptionChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        with transaction.atomic():
            active_subscriptions = tenant.subscriptions.filter(status=TenantPlanSubscription.STATUS_ACTIVE)
            for old_subscription in active_subscriptions:
                old_subscription.status = TenantPlanSubscription.STATUS_CANCELLED
                old_subscription.end_date = timezone.localdate()
                old_subscription.save(update_fields=["status", "end_date", "updated_at"])

            trial_ends_at = None
            if payload["is_trial"]:
                trial_ends_at = timezone.localdate() + timedelta(days=payload["trial_days"])

            subscription = TenantPlanSubscription(
                tenant=tenant,
                plan=payload["plan"],
                is_trial=payload["is_trial"],
                trial_ends_at=trial_ends_at,
                is_courtesy=payload["is_courtesy"],
                setup_fee_override=payload.get("setup_fee_override"),
                status=TenantPlanSubscription.STATUS_ACTIVE,
            )
            subscription.full_clean()
            subscription.save()

            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_UPDATE,
                {
                    "resource": "subscription",
                    "tenant_id": tenant.id,
                    "plan_id": payload["plan"].id,
                    "is_trial": payload["is_trial"],
                    "trial_days": payload.get("trial_days"),
                    "is_courtesy": payload["is_courtesy"],
                    "setup_fee_override": str(payload.get("setup_fee_override")),
                },
            )

        tenant.refresh_from_db()
        return Response(ControlPanelTenantSerializer(tenant).data)

    @action(detail=True, methods=["get", "post"], url_path="contracts")
    def contracts(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)

        if request.method.lower() == "get":
            queryset = tenant.contracts.order_by("-created_at")
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_LIST,
                {"resource": "contract", "tenant_id": tenant.id, "result_count": queryset.count()},
            )
            return Response(TenantContractDocumentSerializer(queryset, many=True).data)

        contract = generate_contract(tenant.id)
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_CREATE,
            {"resource": "contract", "tenant_id": tenant.id, "contract_id": contract.id},
        )
        return Response(
            TenantContractDocumentSerializer(contract).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="monitoring")
    def monitoring(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        period_label, since = _parse_monitoring_period(request.query_params.get("period"))
        history_queryset = tenant.health_snapshots.order_by("-captured_at")
        if since is not None:
            history_queryset = history_queryset.filter(captured_at__gte=since)
        latest_snapshot = (
            history_queryset.first()
        )
        history = history_queryset[:100]
        open_alerts = tenant.alerts.filter(status=TenantAlertEvent.STATUS_OPEN).order_by("-last_seen_at")[:50]

        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_RETRIEVE,
            {
                "resource": "monitoring",
                "tenant_id": tenant.id,
                "history_count": len(history),
                "period": period_label,
            },
        )
        return Response(
            {
                "tenant": ControlPanelTenantSerializer(tenant).data,
                "period": period_label,
                "latest": (
                    TenantHealthSnapshotSerializer(latest_snapshot).data
                    if latest_snapshot
                    else None
                ),
                "history": TenantHealthSnapshotSerializer(history, many=True).data,
                "alerts": TenantAlertEventSerializer(open_alerts, many=True).data,
            }
        )

    @action(detail=True, methods=["get"], url_path="audit")
    def audit(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        events = (
            AdminAuditEvent.objects.select_related("actor", "target_tenant")
            .filter(target_tenant=tenant)
            .order_by("-created_at")[:200]
        )
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_LIST,
            {
                "resource": "admin_audit_event",
                "tenant_id": tenant.id,
                "result_count": len(events),
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(AdminAuditEventSerializer(events, many=True).data)

    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method.lower() == "get":
            notes = tenant.internal_notes.select_related("created_by").order_by("-created_at")[:200]
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_LIST,
                {
                    "resource": "tenant_internal_note",
                    "tenant_id": tenant.id,
                    "result_count": len(notes),
                    "correlation_id": getattr(request, "correlation_id", ""),
                },
            )
            return Response(TenantInternalNoteSerializer(notes, many=True).data)

        serializer = TenantInternalNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = TenantInternalNote.objects.create(
            tenant=tenant,
            note=serializer.validated_data["note"],
            created_by=request.user if request.user.is_authenticated else None,
        )
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_CREATE,
            {
                "resource": "tenant_internal_note",
                "tenant_id": tenant.id,
                "entity_id": note.id,
                "before": {},
                "after": {"note": note.note},
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(
            TenantInternalNoteSerializer(note).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="features")
    def features(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method.lower() == "get":
            features = FeatureFlag.objects.order_by("name")
            current_flags = {
                row.feature_id: row
                for row in tenant.feature_flags.select_related("feature", "updated_by")
            }
            payload = []
            for feature in features:
                flag = current_flags.get(feature.id)
                payload.append(
                    {
                        "id": flag.id if flag else None,
                        "tenant": tenant.id,
                        "feature": FeatureFlagSerializer(feature).data,
                        "enabled": bool(flag.enabled) if flag else False,
                        "updated_by": flag.updated_by_id if flag else None,
                        "updated_by_username": (
                            flag.updated_by.username
                            if flag and flag.updated_by is not None
                            else None
                        ),
                        "created_at": flag.created_at if flag else None,
                        "updated_at": flag.updated_at if flag else None,
                    }
                )

            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_LIST,
                {
                    "resource": "tenant_feature_flag",
                    "tenant_id": tenant.id,
                    "result_count": len(payload),
                    "correlation_id": getattr(request, "correlation_id", ""),
                },
            )
            return Response(payload)

        serializer = TenantFeatureFlagWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feature = get_object_or_404(
            FeatureFlag,
            key=serializer.validated_data["feature_key"],
        )
        with transaction.atomic():
            flag, created = TenantFeatureFlag.objects.select_for_update().get_or_create(
                tenant=tenant,
                feature=feature,
                defaults={
                    "enabled": serializer.validated_data["enabled"],
                    "updated_by": request.user if request.user.is_authenticated else None,
                },
            )
            before_enabled = bool(flag.enabled) if not created else False
            if not created:
                flag.enabled = serializer.validated_data["enabled"]
                flag.updated_by = request.user if request.user.is_authenticated else None
                flag.save(update_fields=["enabled", "updated_by", "updated_at"])

        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "tenant_feature_flag",
                "tenant_id": tenant.id,
                "entity_id": flag.id,
                "before": {"enabled": before_enabled},
                "after": {"enabled": flag.enabled, "feature_key": feature.key},
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(TenantFeatureFlagSerializer(flag).data)

    @action(detail=True, methods=["get", "post"], url_path="limits")
    def limits(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method.lower() == "get":
            settings_obj, _ = TenantOperationalSettings.objects.get_or_create(tenant=tenant)
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_RETRIEVE,
                {"resource": "tenant_limits", "tenant_id": tenant.id},
            )
            return Response(TenantOperationalSettingsSerializer(settings_obj).data)

        serializer = TenantOperationalSettingsWriteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        settings_obj, _ = TenantOperationalSettings.objects.get_or_create(tenant=tenant)
        before_data = TenantOperationalSettingsSerializer(settings_obj).data
        for field, value in payload.items():
            setattr(settings_obj, field, value)
        settings_obj.updated_by = request.user if request.user.is_authenticated else None
        settings_obj.full_clean()
        settings_obj.save()

        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "tenant_limits",
                "tenant_id": tenant.id,
                "before": before_data,
                "after": TenantOperationalSettingsSerializer(settings_obj).data,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(TenantOperationalSettingsSerializer(settings_obj).data)

    @action(detail=True, methods=["get", "post"], url_path="integrations")
    def integrations(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method.lower() == "get":
            queryset = tenant.integration_secrets.select_related("created_by").order_by("provider", "alias")
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_LIST,
                {"resource": "tenant_integration_secret_ref", "tenant_id": tenant.id, "result_count": queryset.count()},
            )
            return Response(TenantIntegrationSecretRefSerializer(queryset, many=True).data)

        serializer = TenantIntegrationSecretRefWriteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        with transaction.atomic():
            row, created = TenantIntegrationSecretRef.objects.select_for_update().get_or_create(
                tenant=tenant,
                provider=payload["provider"],
                alias=payload["alias"],
                defaults={
                    "secret_manager_ref": payload["secret_manager_ref"],
                    "metadata_json": payload.get("metadata_json", {}),
                    "is_active": payload.get("is_active", True),
                    "created_by": request.user if request.user.is_authenticated else None,
                },
            )
            before_data = (
                {}
                if created
                else TenantIntegrationSecretRefSerializer(row).data
            )
            if not created:
                row.secret_manager_ref = payload["secret_manager_ref"]
                row.metadata_json = payload.get("metadata_json", {})
                row.is_active = payload.get("is_active", True)
                row.full_clean()
                row.save(update_fields=["secret_manager_ref", "metadata_json", "is_active", "updated_at"])

        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_UPDATE if not created else ControlPanelAuditLog.ACTION_CREATE,
            {
                "resource": "tenant_integration_secret_ref",
                "tenant_id": tenant.id,
                "entity_id": row.id,
                "before": before_data,
                "after": TenantIntegrationSecretRefSerializer(row).data,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(TenantIntegrationSecretRefSerializer(row).data, status=status.HTTP_201_CREATED if created else 200)

    @action(detail=True, methods=["get", "post"], url_path="changelog")
    def changelog(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if request.method.lower() == "get":
            queryset = tenant.release_records.select_related("created_by").order_by("-deployed_at", "-id")[:100]
            _audit(
                request.user,
                tenant,
                ControlPanelAuditLog.ACTION_LIST,
                {"resource": "tenant_release_record", "tenant_id": tenant.id, "result_count": len(queryset)},
            )
            return Response(TenantReleaseRecordSerializer(queryset, many=True).data)

        serializer = TenantReleaseRecordWriteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        with transaction.atomic():
            if payload.get("is_current", True):
                tenant.release_records.filter(is_current=True).update(is_current=False)
            record = TenantReleaseRecord.objects.create(
                tenant=tenant,
                backend_version=payload["backend_version"],
                frontend_version=payload.get("frontend_version", ""),
                git_sha=payload.get("git_sha", ""),
                source=payload.get("source", "cloud_run") or "cloud_run",
                changelog=payload.get("changelog", ""),
                changelog_json=payload.get("changelog_json", []),
                is_current=payload.get("is_current", True),
                deployed_at=payload.get("deployed_at", timezone.now()),
                created_by=request.user if request.user.is_authenticated else None,
            )
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_CREATE,
            {
                "resource": "tenant_release_record",
                "tenant_id": tenant.id,
                "entity_id": record.id,
                "after": TenantReleaseRecordSerializer(record).data,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(TenantReleaseRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="alerts")
    def alerts(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        status_filter = (request.query_params.get("status") or "").strip().upper()
        queryset = tenant.alerts.order_by("-last_seen_at")
        if status_filter in {TenantAlertEvent.STATUS_OPEN, TenantAlertEvent.STATUS_RESOLVED}:
            queryset = queryset.filter(status=status_filter)
        queryset = queryset[:200]
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_LIST,
            {
                "resource": "tenant_alert_event",
                "tenant_id": tenant.id,
                "status": status_filter or "ALL",
                "result_count": len(queryset),
            },
        )
        return Response(TenantAlertEventSerializer(queryset, many=True).data)

    @action(detail=True, methods=["post"], url_path="alerts/resolve")
    def resolve_alert(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = TenantAlertResolveSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        alert = get_object_or_404(
            tenant.alerts,
            pk=serializer.validated_data["alert_id"],
        )
        alert.status = TenantAlertEvent.STATUS_RESOLVED
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["status", "resolved_at", "last_seen_at"])
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "tenant_alert_event",
                "tenant_id": tenant.id,
                "entity_id": alert.id,
                "after": {"status": alert.status},
            },
        )
        return Response(TenantAlertEventSerializer(alert).data)

    @action(detail=True, methods=["post"], url_path="impersonate")
    def impersonate(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only SUPERADMIN can start impersonation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = TenantImpersonationStartSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        now = timezone.now()
        TenantImpersonationSession.objects.filter(
            actor=request.user,
            tenant=tenant,
            status=TenantImpersonationSession.STATUS_ACTIVE,
        ).update(
            status=TenantImpersonationSession.STATUS_ENDED,
            ended_at=now,
        )

        session = TenantImpersonationSession.objects.create(
            actor=request.user,
            tenant=tenant,
            reason=payload.get("reason", ""),
            correlation_id=getattr(request, "correlation_id", ""),
            expires_at=now + timedelta(minutes=payload.get("duration_minutes", 30)),
        )

        base_domain = (getattr(settings, "TENANT_BASE_DOMAIN", "") or "").strip().lower()
        portal_url = ""
        if base_domain:
            portal_url = f"https://{tenant.slug}.{base_domain}/tenant/dashboard"

        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_CREATE,
            {
                "resource": "tenant_impersonation",
                "tenant_id": tenant.id,
                "entity_id": session.id,
                "after": {
                    "session_id": session.id,
                    "expires_at": session.expires_at.isoformat(),
                },
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        response_payload = {
            "tenant_code": tenant.slug,
            "portal_url": portal_url,
            "session": TenantImpersonationSessionSerializer(session).data,
        }
        return Response(response_payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="impersonate/stop")
    def stop_impersonation(self, request, pk=None):
        tenant = get_object_or_404(self.get_queryset(), pk=pk)
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only SUPERADMIN can stop impersonation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = TenantImpersonationStopSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data.get("session_id")

        queryset = TenantImpersonationSession.objects.filter(
            actor=request.user,
            tenant=tenant,
            status=TenantImpersonationSession.STATUS_ACTIVE,
        )
        if session_id:
            queryset = queryset.filter(id=session_id)
        count = queryset.update(
            status=TenantImpersonationSession.STATUS_ENDED,
            ended_at=timezone.now(),
        )
        _audit(
            request.user,
            tenant,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "tenant_impersonation",
                "tenant_id": tenant.id,
                "after": {"ended_sessions": count},
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response({"ended_sessions": count})


class ControlPanelPlanViewSet(viewsets.ViewSet):
    permission_classes = [IsControlPanelAdmin]

    def list(self, request):
        plans = Plan.objects.select_related("price").order_by("name")
        data = PlanSerializer(plans, many=True).data
        _audit(request.user, None, ControlPanelAuditLog.ACTION_LIST, {"resource": "plan", "result_count": len(data)})
        return Response(data)

    def create(self, request):
        serializer = PlanWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            with transaction.atomic():
                plan = Plan.objects.create(
                    name=payload["name"],
                    tier=payload["tier"],
                    is_active=payload["is_active"],
                )
                PlanPrice.objects.create(
                    plan=plan,
                    monthly_price=payload["monthly_price"],
                    setup_fee=payload["setup_fee"],
                )
                _audit(
                    request.user,
                    None,
                    ControlPanelAuditLog.ACTION_CREATE,
                    {"resource": "plan", "plan_id": plan.id, "tier": plan.tier},
                )
        except IntegrityError:
            return Response({"detail": "Plan name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        plan = get_object_or_404(Plan.objects.select_related("price"), pk=pk)
        serializer = PlanWriteSerializer(data={**{
            "name": plan.name,
            "tier": plan.tier,
            "is_active": plan.is_active,
            "monthly_price": plan.price.monthly_price if hasattr(plan, "price") else "150.00",
            "setup_fee": plan.price.setup_fee if hasattr(plan, "price") else "0.00",
        }, **request.data})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            with transaction.atomic():
                plan.name = payload["name"]
                plan.tier = payload["tier"]
                plan.is_active = payload["is_active"]
                plan.full_clean()
                plan.save(update_fields=["name", "tier", "is_active", "updated_at"])
                price, _ = PlanPrice.objects.get_or_create(
                    plan=plan,
                    defaults={"monthly_price": payload["monthly_price"], "setup_fee": payload["setup_fee"]},
                )
                price.monthly_price = payload["monthly_price"]
                price.setup_fee = payload["setup_fee"]
                price.full_clean()
                price.save(update_fields=["monthly_price", "setup_fee", "updated_at"])
                _audit(
                    request.user,
                    None,
                    ControlPanelAuditLog.ACTION_UPDATE,
                    {"resource": "plan", "plan_id": plan.id},
                )
        except IntegrityError:
            return Response({"detail": "Plan name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PlanSerializer(plan).data)


class ControlPanelFeatureFlagViewSet(viewsets.ViewSet):
    permission_classes = [IsControlPanelAdmin]

    def list(self, request):
        queryset = FeatureFlag.objects.order_by("name")
        _audit(
            request.user,
            None,
            ControlPanelAuditLog.ACTION_LIST,
            {
                "resource": "feature_flag",
                "result_count": queryset.count(),
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(FeatureFlagSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FeatureFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feature = serializer.save()
        _audit(
            request.user,
            None,
            ControlPanelAuditLog.ACTION_CREATE,
            {
                "resource": "feature_flag",
                "entity_id": feature.id,
                "after": FeatureFlagSerializer(feature).data,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(FeatureFlagSerializer(feature).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        feature = get_object_or_404(FeatureFlag, pk=pk)
        serializer = FeatureFlagSerializer(feature, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before_data = FeatureFlagSerializer(feature).data
        serializer.save()
        _audit(
            request.user,
            None,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "feature_flag",
                "entity_id": feature.id,
                "before": before_data,
                "after": serializer.data,
                "correlation_id": getattr(request, "correlation_id", ""),
            },
        )
        return Response(serializer.data)


class ControlPanelContractViewSet(viewsets.ViewSet):
    permission_classes = [IsControlPanelAdmin]

    def retrieve(self, request, pk=None):
        contract = get_object_or_404(
            TenantContractDocument.objects.select_related("tenant"),
            pk=pk,
        )
        payload = TenantContractDocumentSerializer(contract).data
        payload["email_logs"] = ContractEmailLogSerializer(contract.email_logs.order_by("-id"), many=True).data
        _audit(
            request.user,
            contract.tenant,
            ControlPanelAuditLog.ACTION_RETRIEVE,
            {"resource": "contract", "contract_id": contract.id, "tenant_id": contract.tenant_id},
        )
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        contract = get_object_or_404(
            TenantContractDocument.objects.select_related("tenant"),
            pk=pk,
        )
        serializer = ContractSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = send_contract_email(
                contract.id,
                to_email=serializer.validated_data["to_email"],
                force_send=serializer.validated_data["force_send"],
            )
        except ContractServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        _audit(
            request.user,
            contract.tenant,
            ControlPanelAuditLog.ACTION_UPDATE,
            {
                "resource": "contract",
                "contract_id": contract.id,
                "tenant_id": contract.tenant_id,
                "email_log_id": result.email_log.id,
            },
        )
        payload = TenantContractDocumentSerializer(result.contract).data
        payload["email_log"] = ContractEmailLogSerializer(result.email_log).data
        return Response(payload)


class ControlPanelMonitoringViewSet(viewsets.ViewSet):
    permission_classes = [IsControlPanelAdmin]

    def list(self, request):
        period_label, since = _parse_monitoring_period(request.query_params.get("period"))
        heartbeat_threshold_minutes = max(
            1,
            int(getattr(settings, "CONTROL_PLANE_ALERT_HEARTBEAT_MINUTES", 15)),
        )
        high_error_threshold = float(
            getattr(settings, "CONTROL_PLANE_ALERT_HIGH_ERROR_RATE", 0.10)
        )

        system_snapshots = SystemHealthSnapshot.objects.order_by("service_name", "-captured_at")
        if since is not None:
            system_snapshots = system_snapshots.filter(captured_at__gte=since)
        latest_by_service = {}
        for snapshot in system_snapshots:
            if snapshot.service_name in latest_by_service:
                continue
            latest_by_service[snapshot.service_name] = snapshot

        tenant_latest = {}
        tenant_snapshots = (
            TenantHealthSnapshot.objects.select_related("tenant")
            .order_by("tenant_id", "-captured_at")
        )
        if since is not None:
            tenant_snapshots = tenant_snapshots.filter(captured_at__gte=since)
        for snapshot in tenant_snapshots:
            if snapshot.tenant_id in tenant_latest:
                continue
            tenant_latest[snapshot.tenant_id] = snapshot

        latest_tenant_rows = list(tenant_latest.values())
        stale_before = timezone.now() - timedelta(minutes=heartbeat_threshold_minutes)
        degraded_count = sum(
            1
            for row in latest_tenant_rows
            if row.error_rate > 0 or row.p95_latency > 1200 or row.jobs_pending > 20
        )

        for row in latest_tenant_rows:
            if row.last_seen_at is None or row.last_seen_at < stale_before:
                _mark_alert_open(
                    row.tenant,
                    alert_type=TenantAlertEvent.TYPE_NO_HEARTBEAT,
                    severity=TenantAlertEvent.SEVERITY_CRITICAL,
                    message=(
                        f"Tenant sem heartbeat recente. Último heartbeat: "
                        f"{row.last_seen_at.isoformat() if row.last_seen_at else 'nunca'}."
                    ),
                    metrics_json={
                        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
                        "threshold_minutes": heartbeat_threshold_minutes,
                    },
                )
            else:
                _resolve_open_alert(row.tenant, TenantAlertEvent.TYPE_NO_HEARTBEAT)

            if row.error_rate >= high_error_threshold:
                _mark_alert_open(
                    row.tenant,
                    alert_type=TenantAlertEvent.TYPE_HIGH_ERROR_RATE,
                    severity=TenantAlertEvent.SEVERITY_WARNING,
                    message=f"Taxa de erro alta detectada: {row.error_rate:.4f}.",
                    metrics_json={
                        "error_rate": row.error_rate,
                        "threshold": high_error_threshold,
                    },
                )
            else:
                _resolve_open_alert(row.tenant, TenantAlertEvent.TYPE_HIGH_ERROR_RATE)

        open_alerts = TenantAlertEvent.objects.filter(status=TenantAlertEvent.STATUS_OPEN).select_related("tenant")

        _audit(
            request.user,
            None,
            ControlPanelAuditLog.ACTION_LIST,
            {
                "resource": "monitoring",
                "service_count": len(latest_by_service),
                "tenant_count": len(latest_tenant_rows),
                "period": period_label,
                "open_alerts": open_alerts.count(),
            },
        )
        return Response(
            {
                "period": period_label,
                "services": SystemHealthSnapshotSerializer(
                    list(latest_by_service.values()), many=True
                ).data,
                "tenants": TenantHealthSnapshotSerializer(latest_tenant_rows, many=True).data,
                "summary": {
                    "total_services": len(latest_by_service),
                    "total_tenants": len(latest_tenant_rows),
                    "degraded_tenants": degraded_count,
                    "open_alerts": open_alerts.count(),
                },
                "alerts": TenantAlertEventSerializer(open_alerts[:200], many=True).data,
            }
        )
