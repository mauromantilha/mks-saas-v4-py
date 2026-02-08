from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from control_plane.models import TenantContract, TenantProvisioning
from control_plane.permissions import IsPlatformAdmin
from control_plane.serializers import (
    TenantControlPlaneCreateSerializer,
    TenantControlPlaneReadSerializer,
    TenantControlPlaneUpdateSerializer,
    TenantProvisionActionSerializer,
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
        "isolation_model": TenantProvisioning.ISOLATION_DATABASE_PER_TENANT,
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
            return Response(
                {"detail": str(exc)},
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
