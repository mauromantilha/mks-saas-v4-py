from django.utils import timezone
from rest_framework import serializers

from finance.models import Payable, ReceivableInstallment, ReceivableInvoice


class PayableSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source="recipient.username", read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Payable
        fields = (
            "id",
            "recipient",
            "recipient_name",
            "beneficiary_name",
            "amount",
            "due_date",
            "description",
            "status",
            "source_ref",
            "is_overdue",
            "days_overdue",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "recipient_name",
            "is_overdue",
            "days_overdue",
            "created_at",
            "updated_at",
        )

    def get_is_overdue(self, obj: Payable) -> bool:
        if obj.status != Payable.STATUS_OPEN:
            return False
        return obj.due_date < timezone.localdate()

    def get_days_overdue(self, obj: Payable) -> int:
        if not self.get_is_overdue(obj):
            return 0
        return (timezone.localdate() - obj.due_date).days


class ReceivableInstallmentSerializer(serializers.ModelSerializer):
    invoice_id = serializers.IntegerField(source="invoice_id", read_only=True)
    invoice_status = serializers.CharField(source="invoice.status", read_only=True)
    policy_id = serializers.IntegerField(source="invoice.policy_id", read_only=True)
    policy_number = serializers.CharField(source="invoice.policy.policy_number", read_only=True)
    insurer_id = serializers.IntegerField(source="invoice.policy.insurer_id", read_only=True)
    insurer_name = serializers.CharField(source="invoice.policy.insurer.name", read_only=True)
    payer_id = serializers.IntegerField(source="invoice.payer_id", read_only=True)
    payer_name = serializers.CharField(source="invoice.payer.name", read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ReceivableInstallment
        fields = (
            "id",
            "invoice_id",
            "invoice_status",
            "policy_id",
            "policy_number",
            "insurer_id",
            "insurer_name",
            "payer_id",
            "payer_name",
            "number",
            "amount",
            "due_date",
            "status",
            "is_overdue",
            "days_overdue",
            "created_at",
            "updated_at",
        )

    def get_is_overdue(self, obj: ReceivableInstallment) -> bool:
        if obj.status != ReceivableInstallment.STATUS_OPEN:
            return False
        return obj.due_date < timezone.localdate()

    def get_days_overdue(self, obj: ReceivableInstallment) -> int:
        if not self.get_is_overdue(obj):
            return 0
        return (timezone.localdate() - obj.due_date).days


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


class ReceivableInstallmentSettleSerializer(serializers.Serializer):
    payment_date = serializers.DateField(required=False)
