from __future__ import annotations

from rest_framework import viewsets

from insurance_core.api.serializers.product import ProductCoverageSerializer
from insurance_core.models import ProductCoverage
from insurance_core.services.product_service import delete_coverage, upsert_coverage
from tenancy.permissions import IsTenantRoleAllowed


class ProductCoverageViewSet(viewsets.ModelViewSet):
    serializer_class = ProductCoverageSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "product_coverages"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return ProductCoverage.objects.none()

        queryset = ProductCoverage.all_objects.filter(company=company).select_related("product")

        product_id = self.request.query_params.get("product_id")
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except ValueError:
                return queryset.none()

        return queryset.order_by("product_id", "code", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        coverage = upsert_coverage(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = coverage

    def perform_update(self, serializer):
        coverage = upsert_coverage(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = coverage

    def perform_destroy(self, instance):
        delete_coverage(
            company=self.request.company,
            actor=self.request.user,
            coverage=instance,
            request=self.request,
        )

