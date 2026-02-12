from rest_framework import serializers

from customers.models import CompanyMembership, ProducerProfile


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


class ProducerProfileReadSerializer(serializers.ModelSerializer):
    membership_id = serializers.IntegerField(source="membership.id", read_only=True)
    user_id = serializers.IntegerField(source="membership.user.id", read_only=True)
    username = serializers.CharField(source="membership.user.username", read_only=True)
    email = serializers.EmailField(source="membership.user.email", read_only=True)
    role = serializers.CharField(source="membership.role", read_only=True)
    membership_is_active = serializers.BooleanField(source="membership.is_active", read_only=True)

    class Meta:
        model = ProducerProfile
        fields = (
            "id",
            "membership_id",
            "user_id",
            "username",
            "email",
            "role",
            "membership_is_active",
            "full_name",
            "cpf",
            "team_name",
            "is_team_manager",
            "zip_code",
            "state",
            "city",
            "neighborhood",
            "street",
            "street_number",
            "address_complement",
            "commission_transfer_percent",
            "payout_hold_days",
            "bank_code",
            "bank_name",
            "bank_agency",
            "bank_account",
            "bank_account_type",
            "pix_key_type",
            "pix_key",
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


class ProducerProfileUpsertSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=CompanyMembership.ROLE_CHOICES, default=CompanyMembership.ROLE_MEMBER)
    is_active = serializers.BooleanField(default=True)

    full_name = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    team_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    is_team_manager = serializers.BooleanField(default=False)
    zip_code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    state = serializers.CharField(max_length=60, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    neighborhood = serializers.CharField(max_length=120, required=False, allow_blank=True)
    street = serializers.CharField(max_length=255, required=False, allow_blank=True)
    street_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    address_complement = serializers.CharField(max_length=120, required=False, allow_blank=True)

    commission_transfer_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    payout_hold_days = serializers.IntegerField(min_value=0, max_value=30, default=3)

    bank_code = serializers.CharField(max_length=4, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    bank_agency = serializers.CharField(max_length=20, required=False, allow_blank=True)
    bank_account = serializers.CharField(max_length=30, required=False, allow_blank=True)
    bank_account_type = serializers.ChoiceField(
        choices=ProducerProfile.ACCOUNT_TYPE_CHOICES,
        required=False,
        allow_blank=True,
    )
    pix_key_type = serializers.ChoiceField(
        choices=ProducerProfile.PIX_KEY_TYPE_CHOICES,
        required=False,
        allow_blank=True,
    )
    pix_key = serializers.CharField(max_length=140, required=False, allow_blank=True)

    def validate(self, attrs):
        username = (attrs.get("username") or "").strip()
        full_name = (attrs.get("full_name") or "").strip()
        cpf = (attrs.get("cpf") or "").strip()
        if not username:
            base = cpf or full_name.lower().replace(" ", ".")
            attrs["username"] = base
        else:
            attrs["username"] = username
        attrs["full_name"] = full_name
        attrs["cpf"] = cpf
        return attrs


class ProducerProfilePatchSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CompanyMembership.ROLE_CHOICES, required=False)
    is_active = serializers.BooleanField(required=False)
    full_name = serializers.CharField(max_length=255, required=False)
    team_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    is_team_manager = serializers.BooleanField(required=False)
    zip_code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    state = serializers.CharField(max_length=60, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    neighborhood = serializers.CharField(max_length=120, required=False, allow_blank=True)
    street = serializers.CharField(max_length=255, required=False, allow_blank=True)
    street_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    address_complement = serializers.CharField(max_length=120, required=False, allow_blank=True)
    commission_transfer_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
    )
    payout_hold_days = serializers.IntegerField(min_value=0, max_value=30, required=False)
    bank_code = serializers.CharField(max_length=4, required=False, allow_blank=True)
    bank_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    bank_agency = serializers.CharField(max_length=20, required=False, allow_blank=True)
    bank_account = serializers.CharField(max_length=30, required=False, allow_blank=True)
    bank_account_type = serializers.ChoiceField(
        choices=ProducerProfile.ACCOUNT_TYPE_CHOICES,
        required=False,
        allow_blank=True,
    )
    pix_key_type = serializers.ChoiceField(
        choices=ProducerProfile.PIX_KEY_TYPE_CHOICES,
        required=False,
        allow_blank=True,
    )
    pix_key = serializers.CharField(max_length=140, required=False, allow_blank=True)

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
