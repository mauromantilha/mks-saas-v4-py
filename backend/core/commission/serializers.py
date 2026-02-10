from rest_framework import serializers
from commission.models import ParticipantProfile


class ParticipantProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = ParticipantProfile
        fields = (
            "id",
            "user",
            "username",
            "email",
            "participant_type",
            "payout_rules",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_user(self, value):
        request = self.context.get("request")
        if request and hasattr(request, "company"):
            # Ensure user belongs to the tenant (via CompanyMembership)
            from customers.models import CompanyMembership
            
            if not CompanyMembership.objects.filter(company=request.company, user=value).exists():
                 raise serializers.ValidationError("User is not a member of this tenant.")
        return value