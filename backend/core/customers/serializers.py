from rest_framework import serializers

from customers.models import CompanyMembership


class CompanyMembershipReadSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "user_id",
            "username",
            "email",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        )


class CompanyMembershipUpsertSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=CompanyMembership.ROLE_CHOICES)
    is_active = serializers.BooleanField(default=True)


class CompanyMembershipUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CompanyMembership.ROLE_CHOICES, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Send at least one field to update.")
        return attrs
