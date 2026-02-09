from __future__ import annotations

from rest_framework import serializers

from finance.fiscal.models import FiscalCustomerSnapshot, FiscalDocument, FiscalJob


class FiscalCustomerSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalCustomerSnapshot
        fields = ("name", "cpf_cnpj", "address")


class FiscalJobSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalJob
        fields = ("status", "attempts", "next_retry_at", "last_error")
        read_only_fields = fields


class FiscalDocumentSerializer(serializers.ModelSerializer):
    customer_snapshot = FiscalCustomerSnapshotSerializer(read_only=True)
    job = FiscalJobSummarySerializer(read_only=True)
    has_xml = serializers.SerializerMethodField()

    class Meta:
        model = FiscalDocument
        fields = (
            "id",
            "invoice_id",
            "provider_document_id",
            "number",
            "series",
            "issue_date",
            "amount",
            "status",
            "xml_document_id",
            "has_xml",
            "job",
            "customer_snapshot",
            "created_at",
            "updated_at",
        )

    def get_has_xml(self, obj: FiscalDocument) -> bool:
        return bool((obj.xml_content or "").strip())


class IssueFiscalSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField(min_value=1)
