from decimal import Decimal
from rest_framework import serializers
from insurance_core.models import Endorsement, Policy, PolicyBillingConfig, Insurer, InsuranceProduct, InsuranceBranch, Claim, PolicyDocument
from operational.models import Customer


class EndorsementSerializer(serializers.ModelSerializer):
    endorsement_type_display = serializers.CharField(source="get_endorsement_type_display", read_only=True)

    class Meta:
        model = Endorsement
        fields = (
            "id",
            "endorsement_type",
            "endorsement_type_display",
            "premium_delta",
            "issue_date",
            "effective_date",
            "description",
            "created_at",
        )
        read_only_fields = ("id", "issue_date", "created_at")


class EndorsementCreateSerializer(serializers.Serializer):
    endorsement_type = serializers.ChoiceField(choices=Endorsement.TYPE_CHOICES)
    effective_date = serializers.DateField()
    premium_delta = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    description = serializers.CharField(required=False, allow_blank=True)


class PolicyBillingConfigSerializer(serializers.ModelSerializer):
    installment_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, write_only=True
    )

    class Meta:
        model = PolicyBillingConfig
        fields = (
            "first_installment_due_date",
            "installments_count",
            "premium_total",
            "installment_amount",
            "commission_rate_percent",
            "original_premium_total",
        )

    def validate(self, attrs):
        premium = attrs.get("premium_total")
        inst_amount = attrs.get("installment_amount")
        count = attrs.get("installments_count")

        if inst_amount and count:
            calculated = inst_amount * count
            if not premium:
                attrs["premium_total"] = calculated
            elif abs(calculated - premium) > Decimal("0.10"):
                raise serializers.ValidationError("Valor da parcela x parcelas não corresponde ao prêmio total.")
        
        attrs.pop("installment_amount", None)
        return attrs


class PolicySerializer(serializers.ModelSerializer):
    billing_config = PolicyBillingConfigSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    insurer_name = serializers.CharField(source="insurer.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    producer_name = serializers.CharField(source="producer.username", read_only=True)
    documents = PolicyDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Policy
        fields = (
            "id",
            "policy_number",
            "customer",
            "customer_name",
            "producer",
            "producer_name",
            "insurer",
            "insurer_name",
            "product",
            "product_name",
            "branch",
            "branch_name",
            "start_date",
            "end_date",
            "issue_date",
            "status",
            "is_renewal",
            "billing_config",
            "documents",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "issue_date", "created_at", "updated_at")

    def validate(self, attrs):
        # Prevent editing critical fields if issued
        if self.instance and self.instance.status in (Policy.STATUS_ISSUED, Policy.STATUS_CANCELLED, Policy.STATUS_EXPIRED):
            for field in ("start_date", "end_date", "customer", "insurer", "product", "branch"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(f"Cannot edit {field} after policy is issued.")

        # Date validation
        start = attrs.get("start_date", self.instance.start_date if self.instance else None)
        end = attrs.get("end_date", self.instance.end_date if self.instance else None)
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "Data final deve ser posterior à data inicial."})
        
        return attrs
    
    def update(self, instance, validated_data):
        billing_data = validated_data.pop("billing_config", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if billing_data:
            # Update or create billing config
            PolicyBillingConfig.objects.update_or_create(
                policy=instance,
                defaults=billing_data
            )
        return instance


class PolicyCreateSerializer(serializers.ModelSerializer):
    billing_config = PolicyBillingConfigSerializer()

    class Meta:
        model = Policy
        fields = (
            "customer",
            "producer",
            "insurer",
            "product",
            "branch",
            "policy_number",
            "start_date",
            "end_date",
            "is_renewal",
            "billing_config",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and hasattr(request, "company"):
            self.fields["customer"].queryset = Customer.objects.filter(company=request.company)
            self.fields["insurer"].queryset = Insurer.objects.filter(company=request.company)
            self.fields["product"].queryset = InsuranceProduct.objects.filter(company=request.company)
            self.fields["branch"].queryset = InsuranceBranch.objects.filter(company=request.company)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "Data final deve ser posterior à data inicial."})
        
        product = attrs.get("product")
        branch = attrs.get("branch")
        if product and branch and product.branch != branch:
             raise serializers.ValidationError({"product": "O ramo do produto não corresponde ao ramo selecionado."})
        return attrs

    def create(self, validated_data):
        billing_data = validated_data.pop("billing_config")
        policy = Policy.objects.create(**validated_data)
        PolicyBillingConfig.objects.create(policy=policy, company=policy.company, **billing_data)
        return policy


class EndorsementSimulationSerializer(serializers.Serializer):
    endorsement_type = serializers.ChoiceField(choices=Endorsement.TYPE_CHOICES)
    effective_date = serializers.DateField()
    premium_delta = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=0)


class InstallmentPreviewSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    due_date = serializers.DateField()
    original_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    new_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    delta = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField()


class ClaimSerializer(serializers.ModelSerializer):
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

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
            "status_display",
            "status_notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "amount_paid", "created_at", "updated_at")


class ClaimCreateSerializer(serializers.Serializer):
    occurrence_date = serializers.DateField()
    report_date = serializers.DateField()
    description = serializers.CharField()
    amount_claimed = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    claim_number = serializers.CharField(max_length=50, required=False)


class ClaimTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Claim.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    amount_approved = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)


class DocumentUploadRequestSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=0)
    checksum = serializers.CharField(max_length=64, required=False, allow_blank=True)
    document_type = serializers.ChoiceField(choices=PolicyDocument.TYPE_CHOICES, required=False)


class GenericDocumentUploadRequestSerializer(DocumentUploadRequestSerializer):
    ENTITY_CHOICES = (
        ("POLICY", "Apólice"),
        ("ENDORSEMENT", "Endosso"),
        ("CLAIM", "Sinistro"),
    )
    entity_type = serializers.ChoiceField(choices=ENTITY_CHOICES)
    entity_id = serializers.IntegerField()


class PolicyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDocument
        fields = (
            "id",
            "document_type",
            "file_name",
            "content_type",
            "file_size",
            "uploaded_at",
            "created_at",
            "endorsement",
            "claim",
        )
        read_only_fields = ("id", "uploaded_at", "created_at", "endorsement", "claim")


class PolicyRenewSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    policy_number = serializers.CharField(max_length=100, required=False)
    premium_total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "Data final deve ser posterior à data inicial."})
        return attrs