from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from control_plane.models import SystemHealthSnapshot, Tenant, TenantHealthSnapshot, TenantContract, TenantProvisioning
from control_plane.permissions import IsControlPanelAdmin, IsPlatformAdmin
from control_plane.provisioning import execute_tenant_provisioning
from control_plane.services.cep_lookup import CepLookupError, lookup_cep
from control_plane.serializers import (
    MonitoringHeartbeatSerializer,
    TenantControlPlaneCreateSerializer,
    TenantControlPlaneReadSerializer,
    TenantControlPlaneUpdateSerializer,
    TenantProvisionActionSerializer,
    TenantProvisionExecuteSerializer,
)
from customers.models import Company


def default_contract_values() -> dict:
    return {
        "plan": TenantContract.PLAN_STARTER,
        "status": TenantContract.STATUS_TRIAL,
        "seats": 3,
        "monthly_fee": 0,
        "start_date": timezone.localdate(),
        "auto_renew": True,
        "notes": "",
    }


def default_provisioning_values(company: Company) -> dict:
    tenant_slug = company.tenant_code.replace("-", "_")
    return {
        # Current architecture: shared DB, isolated schemas via django-tenants.
        "isolation_model": TenantProvisioning.ISOLATION_SCHEMA_PER_TENANT,
        "status": TenantProvisioning.STATUS_PENDING,
        "database_alias": company.tenant_code,
        "database_name": f"crm_{tenant_slug}",
        "database_host": "127.0.0.1",
        "database_port": 5432,
        "database_user": f"{tenant_slug}_user",
        "database_password_secret": "",
        "portal_url": "",
        "last_error": "",
    }


class ControlPlaneTenantListCreateAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        queryset = Company.objects.select_related("contract", "provisioning").order_by("name")
        search = request.query_params.get("q", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        serializer = TenantControlPlaneReadSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TenantControlPlaneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company_data = {
            "name": payload["name"],
            "tenant_code": payload["tenant_code"],
            "subdomain": payload["subdomain"],
            "is_active": payload.get("is_active", True),
        }
        contract_data = {**default_contract_values(), **payload.get("contract", {})}
        provisioning_data = payload.get("provisioning", {})

        try:
            with transaction.atomic():
                company = Company.objects.create(**company_data)
                TenantContract.objects.create(company=company, **contract_data)

                base_provisioning = default_provisioning_values(company)
                TenantProvisioning.objects.create(
                    company=company,
                    **{**base_provisioning, **provisioning_data},
                )
        except IntegrityError as exc:
            # SECURITY: Do not expose database error details to client
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Tenant creation integrity error: {exc}")
            return Response(
                {"detail": "Tenant name, code, or subdomain already exists. Please use a unique identifier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        read_serializer = TenantControlPlaneReadSerializer(company)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class ControlPlaneTenantDetailAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, company_id):
        company = get_object_or_404(
            Company.objects.select_related("contract", "provisioning"),
            id=company_id,
        )
        serializer = TenantControlPlaneReadSerializer(company)
        return Response(serializer.data)

    def patch(self, request, company_id):
        serializer = TenantControlPlaneUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = get_object_or_404(
            Company.objects.select_related("contract", "provisioning"),
            id=company_id,
        )

        company_fields = []
        for field_name in ("name", "subdomain", "is_active"):
            if field_name in payload:
                setattr(company, field_name, payload[field_name])
                company_fields.append(field_name)

        contract_payload = payload.get("contract")
        provisioning_payload = payload.get("provisioning")

        try:
            with transaction.atomic():
                if company_fields:
                    company.save(update_fields=company_fields + ["updated_at"])

                if contract_payload is not None:
                    contract, _ = TenantContract.objects.get_or_create(
                        company=company,
                        defaults=default_contract_values(),
                    )
                    updated_fields = []
                    for key, value in contract_payload.items():
                        setattr(contract, key, value)
                        updated_fields.append(key)
                    if updated_fields:
                        contract.save(update_fields=updated_fields + ["updated_at"])

                if provisioning_payload is not None:
                    provisioning, _ = TenantProvisioning.objects.get_or_create(
                        company=company,
                        defaults=default_provisioning_values(company),
                    )
                    updated_fields = []
                    for key, value in provisioning_payload.items():
                        setattr(provisioning, key, value)
                        updated_fields.append(key)
                    if updated_fields:
                        provisioning.save(update_fields=updated_fields + ["updated_at"])
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company.refresh_from_db()
        read_serializer = TenantControlPlaneReadSerializer(company)
        return Response(read_serializer.data)


class ControlPlaneTenantProvisionAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, company_id):
        serializer = TenantProvisionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = get_object_or_404(Company, id=company_id)
        provisioning, _ = TenantProvisioning.objects.get_or_create(
            company=company,
            defaults=default_provisioning_values(company),
        )

        provisioning.status = payload["status"]
        if "portal_url" in payload:
            provisioning.portal_url = payload["portal_url"]
        if "last_error" in payload:
            provisioning.last_error = payload["last_error"]
        elif provisioning.status != TenantProvisioning.STATUS_FAILED:
            provisioning.last_error = ""
        if (
            provisioning.status == TenantProvisioning.STATUS_READY
            and provisioning.provisioned_at is None
        ):
            provisioning.provisioned_at = timezone.now()

        provisioning.save(
            update_fields=(
                "status",
                "portal_url",
                "last_error",
                "provisioned_at",
                "updated_at",
            )
        )

        company.refresh_from_db()
        read_serializer = TenantControlPlaneReadSerializer(company)
        return Response(read_serializer.data)


class ControlPlaneTenantProvisionExecuteAPIView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, company_id):
        serializer = TenantProvisionExecuteSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        company = get_object_or_404(Company, id=company_id)
        provisioning, _ = TenantProvisioning.objects.get_or_create(
            company=company,
            defaults=default_provisioning_values(company),
        )
        if "portal_url" in payload:
            provisioning.portal_url = payload["portal_url"]
            provisioning.save(update_fields=("portal_url", "updated_at"))

        result = execute_tenant_provisioning(company, provisioning)
        company.refresh_from_db()
        read_serializer = TenantControlPlaneReadSerializer(company)
        if result.success:
            return Response(read_serializer.data)
        return Response(
            {
                "detail": result.message,
                "provider": result.provider,
                "tenant": read_serializer.data,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ControlPanelCepLookupAPIView(APIView):
    permission_classes = [IsControlPanelAdmin]

    def get(self, request, cep: str):
        try:
            payload = lookup_cep(cep)
        except CepLookupError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


class MonitoringHeartbeatAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        expected_token = (getattr(settings, "MONITORING_INGEST_TOKEN", "") or "").strip()
        if not expected_token:
            return Response(
                {"detail": "Monitoring ingest token is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        provided_token = (request.headers.get("X-Monitoring-Token", "") or "").strip()
        if provided_token != expected_token:
            return Response({"detail": "Invalid monitoring token."}, status=status.HTTP_403_FORBIDDEN)

        serializer = MonitoringHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        metadata = payload.get("metadata_json", {})
        # Avoid storing large/sensitive payloads by keeping only explicit keys.
        if metadata and len(metadata.keys()) > 30:
            metadata = {k: metadata[k] for k in list(metadata.keys())[:30]}

        system_snapshot = SystemHealthSnapshot.objects.create(
            service_name=payload["service_name"],
            status=payload["status"],
            latency_ms=payload.get("latency_ms", 0),
            error_rate=payload.get("error_rate", 0),
            metadata_json=metadata,
        )

        tenant = None
        tenant_id = payload.get("tenant_id")
        tenant_slug = payload.get("tenant_slug")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
        elif tenant_slug:
            tenant = Tenant.objects.filter(slug=tenant_slug).first()

        tenant_snapshot = None
        if tenant is not None:
            tenant_snapshot = TenantHealthSnapshot.objects.create(
                tenant=tenant,
                last_seen_at=payload.get("last_seen_at", timezone.now()),
                request_rate=payload.get("request_rate", 0),
                error_rate=payload.get("error_rate", 0),
                p95_latency=payload.get("p95_latency", payload.get("latency_ms", 0)),
                jobs_pending=payload.get("jobs_pending", 0),
            )

        return Response(
            {
                "status": "ok",
                "system_snapshot_id": system_snapshot.id,
                "tenant_snapshot_id": tenant_snapshot.id if tenant_snapshot else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )
