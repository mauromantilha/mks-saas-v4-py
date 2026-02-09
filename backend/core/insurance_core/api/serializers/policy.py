from __future__ import annotations

from rest_framework import serializers

from insurance_core.models import (
    Endorsement,
    InsuranceProduct,
    Insurer,
    Policy,
    PolicyCoverage,
    PolicyDocumentRequirement,
    PolicyItem,
    ProductCoverage,
)
from tenancy.context import get_current_company


class PolicySerializer(serializers.ModelSerializer):
    insurer_id = serializers.PrimaryKeyRelatedField(
        source="insurer",
        queryset=Insurer.all_objects.all(),
        write_only=True,
    )
    insurer = serializers.SerializerMethodField(read_only=True)

    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=InsuranceProduct.all_objects.all(),
        write_only=True,
    )
    product = serializers.SerializerMethodField(read_only=True)

    status = serializers.ChoiceField(choices=Policy.Status.choices, read_only=True)

    class Meta:
        model = Policy
        fields = (
            "id",
            "policy_number",
            "insurer",
            "insurer_id",
            "product",
            "product_id",
            "insured_party_id",
            "insured_party_label",
            "broker_reference",
            "status",
            "issue_date",
            "start_date",
            "end_date",
            "currency",
            "premium_total",
            "tax_total",
            "commission_total",
            "notes",
            "ai_insights",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "insurer",
            "product",
            "insured_party_label",
            "status",
            "ai_insights",
            "created_by",
            "created_at",
            "updated_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["insurer_id"].queryset = Insurer.all_objects.filter(company=company)
            self.fields["product_id"].queryset = InsuranceProduct.all_objects.filter(company=company)

    def get_insurer(self, obj):
        return {"id": obj.insurer_id, "name": obj.insurer.name}

    def get_product(self, obj):
        return {
            "id": obj.product_id,
            "name": obj.product.name,
            "line_of_business": obj.product.line_of_business,
        }

    def validate_policy_number(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def validate_currency(self, value: str) -> str:
        value = (value or "").strip().upper()
        if not value:
            return "BRL"
        if len(value) != 3:
            raise serializers.ValidationError("currency must be a 3-letter ISO code (ex: BRL).")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "end_date must be >= start_date."})
        return attrs


class PolicyTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Policy.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PolicyItemSerializer(serializers.ModelSerializer):
    policy_id = serializers.PrimaryKeyRelatedField(
        source="policy",
        queryset=Policy.all_objects.all(),
        write_only=True,
    )
    policy = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PolicyItem
        fields = (
            "id",
            "policy",
            "policy_id",
            "item_type",
            "description",
            "attributes",
            "sum_insured",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "policy", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["policy_id"].queryset = Policy.all_objects.filter(company=company)

    def get_policy(self, obj):
        return {"id": obj.policy_id, "policy_number": obj.policy.policy_number}


class PolicyCoverageSerializer(serializers.ModelSerializer):
    policy_id = serializers.PrimaryKeyRelatedField(
        source="policy",
        queryset=Policy.all_objects.all(),
        write_only=True,
    )
    policy = serializers.SerializerMethodField(read_only=True)

    product_coverage_id = serializers.PrimaryKeyRelatedField(
        source="product_coverage",
        queryset=ProductCoverage.all_objects.all(),
        write_only=True,
    )
    product_coverage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PolicyCoverage
        fields = (
            "id",
            "policy",
            "policy_id",
            "product_coverage",
            "product_coverage_id",
            "limit_amount",
            "deductible_amount",
            "premium_amount",
            "is_enabled",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "policy", "product_coverage", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["policy_id"].queryset = Policy.all_objects.filter(company=company)
            self.fields["product_coverage_id"].queryset = ProductCoverage.all_objects.filter(company=company)

    def get_policy(self, obj):
        return {"id": obj.policy_id, "policy_number": obj.policy.policy_number}

    def get_product_coverage(self, obj):
        return {
            "id": obj.product_coverage_id,
            "code": obj.product_coverage.code,
            "name": obj.product_coverage.name,
        }


class PolicyDocumentRequirementSerializer(serializers.ModelSerializer):
    policy_id = serializers.PrimaryKeyRelatedField(
        source="policy",
        queryset=Policy.all_objects.all(),
        write_only=True,
    )
    policy = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PolicyDocumentRequirement
        fields = (
            "id",
            "policy",
            "policy_id",
            "requirement_code",
            "required",
            "status",
            "document_id",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "policy", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["policy_id"].queryset = Policy.all_objects.filter(company=company)

    def get_policy(self, obj):
        return {"id": obj.policy_id, "policy_number": obj.policy.policy_number}


class EndorsementSerializer(serializers.ModelSerializer):
    policy_id = serializers.PrimaryKeyRelatedField(
        source="policy",
        queryset=Policy.all_objects.all(),
        write_only=True,
    )
    policy = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Endorsement
        fields = (
            "id",
            "policy",
            "policy_id",
            "endorsement_number",
            "type",
            "status",
            "effective_date",
            "payload",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "policy", "ai_insights", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = (
            self.context.get("company")
            or getattr(self.context.get("request"), "company", None)
            or get_current_company()
        )
        if company is not None:
            self.fields["policy_id"].queryset = Policy.all_objects.filter(company=company)

    def get_policy(self, obj):
        return {"id": obj.policy_id, "policy_number": obj.policy.policy_number}

