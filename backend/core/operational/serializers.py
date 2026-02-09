from rest_framework import serializers

from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    CustomerContact,
    Endosso,
    Lead,
    Opportunity,
    PolicyRequest,
    ProposalOption,
    SalesGoal,
)


class CustomerContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CustomerContact
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "role",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
        )


class CustomerSerializer(serializers.ModelSerializer):
    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True
    )
    contacts = CustomerContactSerializer(many=True, required=False)

    def validate_contacts(self, value):
        if not value:
            return value
        primary_count = sum(bool(item.get("is_primary")) for item in value)
        if primary_count > 1:
            raise serializers.ValidationError("Only one contact can be marked as primary.")
        return value

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

    def _sync_contacts(self, customer: Customer, contacts_data: list[dict]) -> None:
        existing = {contact.id: contact for contact in customer.contacts.all()}
        keep_ids: set[int] = set()

        for item in contacts_data:
            contact_id = item.get("id")
            if contact_id is None:
                created = CustomerContact.objects.create(customer=customer, **item)
                keep_ids.add(created.id)
                continue

            try:
                contact_id_int = int(contact_id)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    {"contacts": f"Invalid contact id '{contact_id}'."}
                )

            instance = existing.get(contact_id_int)
            if instance is None:
                raise serializers.ValidationError(
                    {
                        "contacts": (
                            f"Contact id '{contact_id_int}' does not exist for this customer."
                        )
                    }
                )

            for field in ("name", "email", "phone", "role", "is_primary", "notes"):
                if field in item:
                    setattr(instance, field, item[field])
            instance.save()
            keep_ids.add(instance.id)

        # Replace semantics: if contacts are provided, any missing contact is deleted.
        for contact_id, contact in existing.items():
            if contact_id not in keep_ids:
                contact.delete()

    def create(self, validated_data):
        contacts_data = validated_data.pop("contacts", [])
        customer = super().create(validated_data)
        if contacts_data:
            self._sync_contacts(customer, contacts_data)
        return customer

    def update(self, instance, validated_data):
        contacts_data = validated_data.pop("contacts", None)
        customer = super().update(instance, validated_data)
        if contacts_data is not None:
            self._sync_contacts(customer, contacts_data)
        return customer

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
            "contacts",
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
            "capture_channel",
            "external_id",
            "external_campaign",
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
            "lead_score_label",
            "product_line",
            "cnae_code",
            "company_size_estimate",
            "raw_payload",
            "needs_summary",
            "needs_payload",
            "first_response_sla_minutes",
            "first_response_due_at",
            "first_response_at",
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
            "product_line",
            "amount",
            "expected_close_date",
            "closing_probability",
            "next_step",
            "next_step_due_at",
            "needs_payload",
            "quote_payload",
            "proposal_pdf_url",
            "proposal_tracking_token",
            "proposal_sent_at",
            "proposal_viewed_at",
            "loss_reason",
            "competitors",
            "handover_notes",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")


class ProposalOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalOption
        fields = (
            "id",
            "opportunity",
            "insurer_name",
            "plan_name",
            "coverage_summary",
            "deductible",
            "annual_premium",
            "monthly_premium",
            "franchise_notes",
            "commission_percent",
            "commission_amount",
            "ranking_score",
            "is_recommended",
            "external_reference",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "ai_insights", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = getattr(request, "company", None)
        opportunity = attrs.get("opportunity", getattr(self.instance, "opportunity", None))
        if company is not None and opportunity is not None and opportunity.company_id != company.id:
            raise serializers.ValidationError("Opportunity belongs to another tenant.")
        return attrs


class PolicyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyRequest
        fields = (
            "id",
            "opportunity",
            "customer",
            "source_lead",
            "product_line",
            "status",
            "inspection_required",
            "inspection_status",
            "inspection_scheduled_at",
            "inspection_notes",
            "billing_method",
            "bank_account_holder",
            "bank_name",
            "bank_branch",
            "bank_account",
            "bank_document",
            "payment_day",
            "final_premium",
            "final_commission",
            "issue_deadline_at",
            "issued_at",
            "notes",
            "ai_insights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "issued_at", "ai_insights", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = getattr(request, "company", None)
        opportunity = attrs.get("opportunity", getattr(self.instance, "opportunity", None))
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        source_lead = attrs.get("source_lead", getattr(self.instance, "source_lead", None))

        if company is not None:
            if opportunity is not None and opportunity.company_id != company.id:
                raise serializers.ValidationError("Opportunity belongs to another tenant.")
            if customer is not None and customer.company_id != company.id:
                raise serializers.ValidationError("Customer belongs to another tenant.")
            if source_lead is not None and source_lead.company_id != company.id:
                raise serializers.ValidationError("Lead belongs to another tenant.")
        return attrs


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


class SalesGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesGoal
        fields = (
            "id",
            "year",
            "month",
            "premium_goal",
            "commission_goal",
            "new_customers_goal",
            "notes",
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
            ("NEW", "Novo/Sem Contato"),
            ("QUALIFICATION", "Qualificação"),
            ("NEEDS_ASSESSMENT", "Levantamento de Necessidades"),
            ("QUOTATION", "Cotação"),
            ("PROPOSAL_PRESENTATION", "Apresentação de Proposta"),
            ("DISCOVERY", "Descoberta (Legado)"),
            ("PROPOSAL", "Proposta (Legado)"),
            ("NEGOTIATION", "Negociação"),
        ),
        required=False,
        default="QUALIFICATION",
    )
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        default=0,
    )
    expected_close_date = serializers.DateField(required=False, allow_null=True)
    create_customer_if_missing = serializers.BooleanField(required=False, default=True)
    create_policy_request = serializers.BooleanField(required=False, default=True)

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
    policy_requests = serializers.DictField(child=serializers.IntegerField())
    activities = serializers.DictField(child=serializers.IntegerField())
    activities_by_priority = serializers.DictField(child=serializers.IntegerField())
    pipeline_value = serializers.DictField(child=serializers.FloatField())
    conversion = serializers.DictField(child=serializers.FloatField())
