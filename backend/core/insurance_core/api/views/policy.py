from __future__ import annotations

from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from insurance_core.api.serializers.policy import (
    EndorsementSerializer,
    PolicyCoverageSerializer,
    PolicyDocumentRequirementSerializer,
    PolicyItemSerializer,
    PolicySerializer,
    PolicyTransitionSerializer,
)
from insurance_core.models import (
    Endorsement,
    Policy,
    PolicyCoverage,
    PolicyDocumentRequirement,
    PolicyItem,
)
from insurance_core.services.policy_service import (
    delete_endorsement,
    delete_policy,
    delete_policy_coverage,
    delete_policy_document_requirement,
    delete_policy_item,
    transition_policy_status,
    upsert_endorsement,
    upsert_policy,
    upsert_policy_coverage,
    upsert_policy_document_requirement,
    upsert_policy_item,
)
from tenancy.permissions import IsTenantRoleAllowed


class PolicyViewSet(viewsets.ModelViewSet):
    serializer_class = PolicySerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return Policy.objects.none()

        queryset = (
            Policy.all_objects.filter(company=company)
            .select_related("insurer", "product")
            .order_by("-start_date", "-id")
        )

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        insurer_id = self.request.query_params.get("insurer_id")
        if insurer_id:
            try:
                queryset = queryset.filter(insurer_id=int(insurer_id))
            except ValueError:
                return queryset.none()

        insured_party_id = self.request.query_params.get("insured_party_id")
        if insured_party_id:
            try:
                queryset = queryset.filter(insured_party_id=int(insured_party_id))
            except ValueError:
                return queryset.none()

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                models.Q(policy_number__icontains=search)
                | models.Q(insured_party_label__icontains=search)
            )

        return queryset

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        policy = upsert_policy(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = policy

    def perform_update(self, serializer):
        policy = upsert_policy(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = policy

    def destroy(self, request, *args, **kwargs):
        policy = self.get_object()
        delete_policy(company=request.company, actor=request.user, policy=policy, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        serializer = PolicyTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        policy = self.get_object()
        updated = transition_policy_status(
            company=request.company,
            actor=request.user,
            policy=policy,
            to_status=serializer.validated_data["status"],
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )

        response_serializer = self.get_serializer(updated)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class PolicyItemViewSet(viewsets.ModelViewSet):
    serializer_class = PolicyItemSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policy_items"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return PolicyItem.objects.none()

        queryset = PolicyItem.all_objects.filter(company=company).select_related("policy")

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            try:
                queryset = queryset.filter(policy_id=int(policy_id))
            except ValueError:
                return queryset.none()

        return queryset.order_by("policy_id", "item_type", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        item = upsert_policy_item(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = item

    def perform_update(self, serializer):
        item = upsert_policy_item(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = item

    def perform_destroy(self, instance):
        delete_policy_item(
            company=self.request.company,
            actor=self.request.user,
            item=instance,
            request=self.request,
        )


class PolicyCoverageViewSet(viewsets.ModelViewSet):
    serializer_class = PolicyCoverageSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policy_coverages"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return PolicyCoverage.objects.none()

        queryset = PolicyCoverage.all_objects.filter(company=company).select_related(
            "policy", "product_coverage"
        )

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            try:
                queryset = queryset.filter(policy_id=int(policy_id))
            except ValueError:
                return queryset.none()

        return queryset.order_by("policy_id", "product_coverage_id", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        coverage = upsert_policy_coverage(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = coverage

    def perform_update(self, serializer):
        coverage = upsert_policy_coverage(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = coverage

    def perform_destroy(self, instance):
        delete_policy_coverage(
            company=self.request.company,
            actor=self.request.user,
            coverage=instance,
            request=self.request,
        )


class PolicyDocumentRequirementViewSet(viewsets.ModelViewSet):
    serializer_class = PolicyDocumentRequirementSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policy_document_requirements"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return PolicyDocumentRequirement.objects.none()

        queryset = PolicyDocumentRequirement.all_objects.filter(company=company).select_related("policy")

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            try:
                queryset = queryset.filter(policy_id=int(policy_id))
            except ValueError:
                return queryset.none()

        return queryset.order_by("policy_id", "status", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        docreq = upsert_policy_document_requirement(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = docreq

    def perform_update(self, serializer):
        docreq = upsert_policy_document_requirement(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = docreq

    def perform_destroy(self, instance):
        delete_policy_document_requirement(
            company=self.request.company,
            actor=self.request.user,
            docreq=instance,
            request=self.request,
        )


class EndorsementViewSet(viewsets.ModelViewSet):
    serializer_class = EndorsementSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "endorsements"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return Endorsement.objects.none()

        queryset = Endorsement.all_objects.filter(company=company).select_related("policy")

        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            try:
                queryset = queryset.filter(policy_id=int(policy_id))
            except ValueError:
                return queryset.none()

        return queryset.order_by("-effective_date", "-id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["company"] = getattr(self.request, "company", None)
        return ctx

    def perform_create(self, serializer):
        endorsement = upsert_endorsement(
            company=self.request.company,
            actor=self.request.user,
            instance=None,
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = endorsement

    def perform_update(self, serializer):
        endorsement = upsert_endorsement(
            company=self.request.company,
            actor=self.request.user,
            instance=self.get_object(),
            data=serializer.validated_data,
            request=self.request,
        )
        serializer.instance = endorsement

    def perform_destroy(self, instance):
        delete_endorsement(
            company=self.request.company,
            actor=self.request.user,
            endorsement=instance,
            request=self.request,
        )

