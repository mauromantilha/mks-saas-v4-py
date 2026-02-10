from rest_framework import serializers
from insurance_core.models import Claim

class ClaimSerializer(serializers.ModelSerializer):
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)

    class Meta:
        model = Claim
        fields = (
            "id",
            "policy",
            "policy_number",
            "claim_number",
            "occurrence_date",
            "report_date",
            "description",
            "amount_claimed",
            "amount_approved",
            "amount_paid",
            "status",
            "status_notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "claim_number",
            "amount_paid",
            "created_at",
            "updated_at",
        )

class ClaimCreateSerializer(serializers.Serializer):
    occurrence_date = serializers.DateField()
    report_date = serializers.DateField()
    description = serializers.CharField()
    amount_claimed = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

class ClaimTransitionSerializer(serializers.Serializer):
    new_status = serializers.ChoiceField(choices=Claim.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    amount_approved = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)