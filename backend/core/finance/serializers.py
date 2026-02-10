from rest_framework import serializers
from finance.models import ReceivableInvoice, ReceivableInstallment


class ReceivableInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceivableInstallment
        fields = (
            "id",
            "number",
            "amount",
            "due_date",
            "status",
        )


class ReceivableInvoiceSerializer(serializers.ModelSerializer):
    installments = ReceivableInstallmentSerializer(many=True, read_only=True)
    payer_name = serializers.CharField(source="payer.name", read_only=True)
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)

    class Meta:
        model = ReceivableInvoice
        fields = (
            "id",
            "payer",
            "payer_name",
            "policy",
            "policy_number",
            "total_amount",
            "status",
            "issue_date",
            "description",
            "installments",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")