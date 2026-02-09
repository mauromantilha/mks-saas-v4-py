from __future__ import annotations

from rest_framework import serializers

from insurance_core.models import InsuranceProduct, Insurer, ProductCoverage
from tenancy.context import get_current_company


class InsuranceProductSerializer(serializers.ModelSerializer):
    insurer_id = serializers.PrimaryKeyRelatedField(
        source="insurer",
        queryset=Insurer.all_objects.all(),
        write_only=True,
    )
    insurer = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InsuranceProduct
        fields = (
            "id",
            "insurer",
            "insurer_id",
            "code",
            "name",
            "line_of_business",
            "status",
            "rules",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "insurer", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["insurer_id"].queryset = Insurer.all_objects.filter(company=company)

    def get_insurer(self, obj):
        return {"id": obj.insurer_id, "name": obj.insurer.name}

    def validate_code(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("code is required.")
        return value

    def validate(self, attrs):
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        insurer = attrs.get("insurer") or getattr(self.instance, "insurer", None)
        code = (attrs.get("code") or getattr(self.instance, "code", "") or "").strip()
        if company and insurer and code:
            qs = InsuranceProduct.all_objects.filter(company=company, insurer=insurer, code=code)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": "Product code must be unique for this insurer within the tenant."}
                )
        return attrs


class ProductCoverageSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=InsuranceProduct.all_objects.all(),
        write_only=True,
    )
    product = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductCoverage
        fields = (
            "id",
            "product",
            "product_id",
            "code",
            "name",
            "coverage_type",
            "default_limit_amount",
            "default_deductible_amount",
            "required",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "product", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["product_id"].queryset = InsuranceProduct.all_objects.filter(company=company)

    def get_product(self, obj):
        return {"id": obj.product_id, "name": obj.product.name}

    def validate_code(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("code is required.")
        return value

    def validate(self, attrs):
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        product = attrs.get("product") or getattr(self.instance, "product", None)
        code = (attrs.get("code") or getattr(self.instance, "code", "") or "").strip()
        if company and product and code:
            qs = ProductCoverage.all_objects.filter(company=company, product=product, code=code)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": "Coverage code must be unique for this product within the tenant."}
                )
        return attrs
