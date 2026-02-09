from __future__ import annotations

from django.db import models
from rest_framework import status, viewsets
from rest_framework.response import Response

from insurance_core.api.serializers.insurer import InsurerSerializer
from insurance_core.models import Insurer
from insurance_core.services.insurer_service import (
    deactivate_insurer,
    upsert_insurer,
)
from tenancy.permissions import IsTenantRoleAllowed


class InsurerViewSet(viewsets.ModelViewSet):
    serializer_class = InsurerSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "insurers"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return Insurer.objects.none()

        queryset = (
            Insurer.all_objects.filter(company=company)
            .prefetch_related("contacts")
            .order_by("name", "id")
        )

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(legal_name__icontains=search)
            )

        return queryset

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        insurer = upsert_insurer(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = insurer

    def perform_update(self, serializer):
        insurer = upsert_insurer(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = insurer

    def destroy(self, request, *args, **kwargs):
        insurer = self.get_object()
        deactivate_insurer(company=request.company, actor=request.user, insurer=insurer, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
