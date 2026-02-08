from rest_framework import serializers

from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    Endosso,
    Lead,
    Opportunity,
)


class CustomerSerializer(serializers.ModelSerializer):
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True
    )

    def validate(self, attrs):
        request = self.context.get("request")
        company = getattr(request, "company", None)
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))

        if company is not None and assigned_to is not None:
            from customers.models import CompanyMembership

            is_member = CompanyMembership.objects.filter(
                company=company,
                user=assigned_to,
                is_active=True,
            ).exists()
            if not is_member:
                raise serializers.ValidationError(
                    "Assigned user is not an active member of this tenant."
                )

        return attrs

    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "email",
            "customer_type",
            "lifecycle_stage",
            "legal_name",
            "trade_name",
            "phone",
            "whatsapp",
            "document",
            "cnpj",
            "cpf",
            "state_registration",
            "municipal_registration",
            "website",
            "linkedin_url",
            "instagram_url",
            "facebook_url",
            "lead_source",
            "industry",
            "company_size",
            "annual_revenue",
            "contact_name",
            "contact_role",
            "secondary_contact_name",
            "secondary_contact_email",
            "secondary_contact_phone",
            "billing_email",
            "billing_phone",
            "zip_code",
            "state",
            "city",
            "neighborhood",
            "street",
            "street_number",
            "address_complement",
            "assigned_to",
            "assigned_to_username",
            "last_contact_at",
            "next_follow_up_at",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "assigned_to_username",
            "ai_insights",
            "created_at",
            "updated_at",
        )


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
            "full_name",
            "job_title",
            "company_name",
            "email",
            "phone",
            "whatsapp",
            "cnpj",
            "website",
            "linkedin_url",
            "instagram_url",
            "customer",
            "status",
            "products_of_interest",
            "estimated_budget",
            "estimated_close_date",
            "qualification_score",
            "disqualification_reason",
            "last_contact_at",
            "next_follow_up_at",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")


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
            "source_lead",
            "title",
            "stage",
            "amount",
            "expected_close_date",
            "closing_probability",
            "next_step",
            "next_step_due_at",
            "loss_reason",
            "competitors",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")


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
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")


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
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")


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
    create_customer_if_missing = serializers.BooleanField(required=False, default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and getattr(request, "company", None) is not None:
            self.fields["customer"].queryset = Customer.all_objects.filter(
                company=request.company
            )


class OpportunityStageUpdateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Opportunity.STAGE_CHOICES)


class CommercialActivitySerializer(serializers.ModelSerializer):
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True
    )
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)
    is_sla_breached = serializers.BooleanField(read_only=True)

    class Meta:
        model = CommercialActivity
        fields = (
            "id",
            "kind",
            "title",
            "description",
            "channel",
            "outcome",
            "status",
            "priority",
            "due_at",
            "reminder_at",
            "reminder_sent",
            "sla_hours",
            "sla_due_at",
            "completed_at",
            "started_at",
            "ended_at",
            "duration_minutes",
            "meeting_url",
            "location",
            "lead",
            "opportunity",
            "assigned_to",
            "assigned_to_username",
            "created_by",
            "created_by_username",
            "is_overdue",
            "is_sla_breached",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "reminder_sent",
            "sla_due_at",
            "completed_at",
            "duration_minutes",
            "created_by",
            "assigned_to_username",
            "created_by_username",
            "is_overdue",
            "is_sla_breached",
            "ai_insights",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        opportunity = attrs.get(
            "opportunity",
            getattr(self.instance, "opportunity", None),
        )
        assigned_to = attrs.get(
            "assigned_to",
            getattr(self.instance, "assigned_to", None),
        )
        if lead is None and opportunity is None:
            raise serializers.ValidationError(
                "Activity must be linked to a lead or an opportunity."
            )

        if (
            lead is not None
            and opportunity is not None
            and lead.company_id != opportunity.company_id
        ):
            raise serializers.ValidationError(
                "Lead and Opportunity must belong to the same tenant."
            )

        request = self.context.get("request")
        company = getattr(request, "company", None)
        if company is not None:
            if lead is not None and lead.company_id != company.id:
                raise serializers.ValidationError("Lead belongs to another tenant.")
            if opportunity is not None and opportunity.company_id != company.id:
                raise serializers.ValidationError("Opportunity belongs to another tenant.")
            if assigned_to is not None:
                from customers.models import CompanyMembership

                is_member = CompanyMembership.objects.filter(
                    company=company,
                    user=assigned_to,
                    is_active=True,
                ).exists()
                if not is_member:
                    raise serializers.ValidationError(
                        "Assigned user is not an active member of this tenant."
                    )
        return attrs


class LeadHistorySerializer(serializers.Serializer):
    lead = LeadSerializer()
    activities = CommercialActivitySerializer(many=True)
    converted_opportunities = OpportunitySerializer(many=True)


class OpportunityHistorySerializer(serializers.Serializer):
    opportunity = OpportunitySerializer()
    activities = CommercialActivitySerializer(many=True)


class AIInsightRequestSerializer(serializers.Serializer):
    focus = serializers.CharField(required=False, allow_blank=True, max_length=500)
    include_cnpj_enrichment = serializers.BooleanField(required=False, default=True)


class CNPJEnrichmentRequestSerializer(serializers.Serializer):
    cnpj = serializers.CharField(required=False, allow_blank=True, max_length=18)


class SalesMetricsPeriodSerializer(serializers.Serializer):
    from_date = serializers.DateField(allow_null=True, required=False)
    to_date = serializers.DateField(allow_null=True, required=False)
    assigned_to_user_id = serializers.IntegerField(allow_null=True, required=False)


class SalesMetricsSerializer(serializers.Serializer):
    tenant_code = serializers.CharField()
    period = SalesMetricsPeriodSerializer()
    lead_funnel = serializers.DictField(child=serializers.IntegerField())
    opportunity_funnel = serializers.DictField(child=serializers.IntegerField())
    activities = serializers.DictField(child=serializers.IntegerField())
    activities_by_priority = serializers.DictField(child=serializers.IntegerField())
    pipeline_value = serializers.DictField(child=serializers.FloatField())
    conversion = serializers.DictField(child=serializers.FloatField())
