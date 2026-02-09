from __future__ import annotations

from django.db import models
from rest_framework import status, viewsets
from rest_framework.response import Response

from insurance_core.api.serializers.product import InsuranceProductSerializer
from insurance_core.models import InsuranceProduct
from insurance_core.services.product_service import deactivate_product, upsert_product
from tenancy.permissions import IsTenantRoleAllowed


class InsuranceProductViewSet(viewsets.ModelViewSet):
    serializer_class = InsuranceProductSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "insurance_products"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return InsuranceProduct.objects.none()

        queryset = InsuranceProduct.all_objects.filter(company=company).select_related("insurer")

        insurer_id = self.request.query_params.get("insurer_id")
        if insurer_id:
            try:
                queryset = queryset.filter(insurer_id=int(insurer_id))
            except ValueError:
                queryset = queryset.none()

        lob = (self.request.query_params.get("line_of_business") or "").strip().upper()
        if lob:
            queryset = queryset.filter(line_of_business=lob)

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(models.Q(name__icontains=search) | models.Q(code__icontains=search))

        return queryset.order_by("line_of_business", "name", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        product = upsert_product(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = product

    def perform_update(self, serializer):
        product = upsert_product(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = product

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        deactivate_product(company=request.company, actor=request.user, product=product, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

