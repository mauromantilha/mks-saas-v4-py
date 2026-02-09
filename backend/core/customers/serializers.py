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


class PasswordResetRequestSerializer(serializers.Serializer):
    """Password reset request payload.

    We intentionally allow either email or username to support different tenant setups.
    """

    email = serializers.EmailField(required=False)
    username = serializers.CharField(max_length=150, required=False)

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip()
        username = (attrs.get("username") or "").strip()
        if not email and not username:
            raise serializers.ValidationError("Send either 'email' or 'username'.")
        attrs["email"] = email
        attrs["username"] = username
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs.get("new_password") != attrs.get("new_password_confirm"):
            raise serializers.ValidationError({"new_password_confirm": ["Passwords do not match."]})
        return attrs
