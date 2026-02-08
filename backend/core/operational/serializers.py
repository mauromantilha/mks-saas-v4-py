from rest_framework import serializers

from operational.models import Apolice, Customer, Endosso, Lead, Opportunity


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "document",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LeadSerializer(serializers.ModelSerializer):
    def validate_status(self, value):
        current = getattr(self.instance, "status", None)
        if current and not Lead.can_transition_status(current, value):
            raise serializers.ValidationError(
                f"Invalid lead status transition: {current} -> {value}."
            )
        return value

    class Meta:
        model = Lead
        fields = (
            "id",
            "source",
            "customer",
            "status",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OpportunitySerializer(serializers.ModelSerializer):
    def validate_stage(self, value):
        current = getattr(self.instance, "stage", None)
        if current and not Opportunity.can_transition_stage(current, value):
            raise serializers.ValidationError(
                f"Invalid opportunity stage transition: {current} -> {value}."
            )
        return value

    class Meta:
        model = Opportunity
        fields = (
            "id",
            "customer",
            "title",
            "stage",
            "amount",
            "expected_close_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ApoliceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Apolice
        fields = (
            "id",
            "numero",
            "seguradora",
            "ramo",
            "cliente_nome",
            "cliente_cpf_cnpj",
            "inicio_vigencia",
            "fim_vigencia",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class EndossoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endosso
        fields = (
            "id",
            "apolice",
            "numero_endosso",
            "tipo",
            "premio_liquido",
            "iof",
            "premio_total",
            "percentual_comissao",
            "valor_comissao",
            "data_emissao",
            "observacoes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LeadConvertSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.none(),
        required=False,
        allow_null=True,
    )
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    stage = serializers.ChoiceField(
        choices=(
            ("DISCOVERY", "Descoberta"),
            ("PROPOSAL", "Proposta"),
            ("NEGOTIATION", "Negociação"),
        ),
        required=False,
        default="DISCOVERY",
    )
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        default=0,
    )
    expected_close_date = serializers.DateField(required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and getattr(request, "company", None) is not None:
            self.fields["customer"].queryset = Customer.all_objects.filter(
                company=request.company
            )


class OpportunityStageUpdateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Opportunity.STAGE_CHOICES)
