from rest_framework import serializers

from operational.models import (
    AiConversation,
    AiMessage,
    AiSuggestion,
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
    SpecialProject,
    SpecialProjectActivity,
    SpecialProjectDocument,
    TenantAIInteraction,
)
from commission.models import (
    CommissionAccrual,
    CommissionPayoutBatch,
    CommissionPlanScope,
    InsurerSettlementBatch,
)


class CustomerSerializer(serializers.ModelSerializer):
    class CustomerContactSerializer(serializers.ModelSerializer):
        id = serializers.IntegerField(required=False)

        class Meta:
            model = CustomerContact
            fields = ("id", "name", "email", "phone", "role", "is_primary", "notes")

    assigned_to_username = serializers.CharField(
        source="assigned_to.username", read_only=True
    )
    contacts = CustomerContactSerializer(many=True, required=False)

    REQUIRED_ADDRESS_FIELDS = ("zip_code", "street", "street_number", "neighborhood", "city", "state")

    @staticmethod
    def _digits_only(value: str) -> str:
        return "".join(ch for ch in (value or "") if ch.isdigit())

    def _is_valid_cpf(self, value: str) -> bool:
        digits = self._digits_only(value)
        if len(digits) != 11 or len(set(digits)) == 1:
            return False
        for size in (9, 10):
            total = sum(int(digits[idx]) * ((size + 1) - idx) for idx in range(size))
            checker = (total * 10) % 11
            checker = 0 if checker == 10 else checker
            if checker != int(digits[size]):
                return False
        return True

    def _is_valid_cnpj(self, value: str) -> bool:
        digits = self._digits_only(value)
        if len(digits) != 14 or len(set(digits)) == 1:
            return False
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        weights2 = [6, *weights1]
        for weights, pos in ((weights1, 12), (weights2, 13)):
            total = sum(int(d) * w for d, w in zip(digits[:pos], weights))
            rem = total % 11
            checker = 0 if rem < 2 else 11 - rem
            if checker != int(digits[pos]):
                return False
        return True

    def validate(self, attrs):
        request = self.context.get("request")
        company = getattr(request, "company", None)
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        customer_type = attrs.get("customer_type", getattr(self.instance, "customer_type", "COMPANY"))
        cpf = attrs.get("cpf", getattr(self.instance, "cpf", ""))
        cnpj = attrs.get("cnpj", getattr(self.instance, "cnpj", ""))
        industry = attrs.get("industry", getattr(self.instance, "industry", ""))
        lead_source = attrs.get("lead_source", getattr(self.instance, "lead_source", ""))
        contacts = attrs.get("contacts")

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

        if self.instance is None:
            for field_name in ("name", "email", *self.REQUIRED_ADDRESS_FIELDS):
                value = attrs.get(field_name, "")
                if not str(value or "").strip():
                    raise serializers.ValidationError({field_name: "Campo obrigatório."})
        else:
            for field_name in ("name", "email", *self.REQUIRED_ADDRESS_FIELDS):
                if field_name in attrs and not str(attrs.get(field_name) or "").strip():
                    raise serializers.ValidationError({field_name: "Campo obrigatório."})

        if customer_type == Customer.TYPE_INDIVIDUAL and (
            self.instance is None or "cpf" in attrs or "customer_type" in attrs
        ):
            if not self._is_valid_cpf(cpf):
                raise serializers.ValidationError({"cpf": "CPF inválido."})
        if customer_type == Customer.TYPE_COMPANY and (
            self.instance is None or "cnpj" in attrs or "customer_type" in attrs
        ):
            if not self._is_valid_cnpj(cnpj):
                raise serializers.ValidationError({"cnpj": "CNPJ inválido."})

        valid_industries = {value for value, _label in Customer.INDUSTRY_CHOICES}
        if industry and industry not in valid_industries:
            raise serializers.ValidationError({"industry": "Segmento inválido."})
        valid_sources = {value for value, _label in Customer.LEAD_SOURCE_CHOICES}
        if lead_source and lead_source not in valid_sources:
            raise serializers.ValidationError({"lead_source": "Origem inválida."})

        if customer_type == Customer.TYPE_COMPANY and contacts is not None:
            if len(contacts) == 0:
                raise serializers.ValidationError(
                    {"contacts": "Pessoa Jurídica exige ao menos um contato."}
                )
            primary_count = sum(1 for c in contacts if c.get("is_primary"))
            if primary_count == 0:
                contacts[0]["is_primary"] = True
            elif primary_count > 1:
                raise serializers.ValidationError(
                    {"contacts": "Defina somente um contato primário."}
                )

        return attrs

    def _sync_contacts(self, customer: Customer, contacts_data):
        if contacts_data is None:
            return
        existing = {item.id: item for item in customer.contacts.all()}
        keep_ids = set()
        for row in contacts_data:
            contact_id = row.pop("id", None)
            if contact_id and contact_id in existing:
                item = existing[contact_id]
                for key, value in row.items():
                    setattr(item, key, value)
                item.company = customer.company
                item.customer = customer
                item.save()
                keep_ids.add(item.id)
            else:
                item = CustomerContact.all_objects.create(
                    company=customer.company,
                    customer=customer,
                    **row,
                )
                keep_ids.add(item.id)
        for item_id, item in existing.items():
            if item_id not in keep_ids:
                item.delete()

    def create(self, validated_data):
        contacts_data = validated_data.pop("contacts", None)
        customer = super().create(validated_data)
        self._sync_contacts(customer, contacts_data)
        return customer

    def update(self, instance, validated_data):
        contacts_data = validated_data.pop("contacts", None)
        customer = super().update(instance, validated_data)
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


class SpecialProjectActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialProjectActivity
        fields = (
            "id",
            "project",
            "title",
            "description",
            "due_date",
            "status",
            "done_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "done_at", "created_at", "updated_at")


class SpecialProjectDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SpecialProjectDocument
        fields = (
            "id",
            "project",
            "title",
            "file",
            "file_url",
            "uploaded_by",
            "uploaded_by_username",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "uploaded_by",
            "uploaded_by_username",
            "file_url",
            "created_at",
            "updated_at",
        )

    def get_file_url(self, obj):
        request = self.context.get("request")
        if not obj.file:
            return ""
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url


class SpecialProjectSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    activities = SpecialProjectActivitySerializer(many=True, read_only=True)
    documents = SpecialProjectDocumentSerializer(many=True, read_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        company = getattr(request, "company", None)

        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        status = attrs.get("status", getattr(self.instance, "status", SpecialProject.STATUS_OPEN))
        loss_reason = attrs.get("loss_reason", getattr(self.instance, "loss_reason", ""))
        prospect_name = attrs.get("prospect_name", getattr(self.instance, "prospect_name", ""))
        prospect_email = attrs.get("prospect_email", getattr(self.instance, "prospect_email", ""))
        prospect_document = attrs.get("prospect_document", getattr(self.instance, "prospect_document", ""))

        if company is not None:
            if customer is not None and customer.company_id != company.id:
                raise serializers.ValidationError("Customer belongs to another tenant.")
            if owner is not None:
                from customers.models import CompanyMembership

                is_member = CompanyMembership.objects.filter(
                    company=company,
                    user=owner,
                    is_active=True,
                ).exists()
                if not is_member:
                    raise serializers.ValidationError("Owner must be an active tenant member.")

        if customer is None:
            if not str(prospect_name or "").strip():
                raise serializers.ValidationError(
                    {"prospect_name": "Informe nome do cliente para o projeto."}
                )
            if not str(prospect_email or "").strip():
                raise serializers.ValidationError(
                    {"prospect_email": "Informe email do cliente para o projeto."}
                )
            if not str(prospect_document or "").strip():
                raise serializers.ValidationError(
                    {"prospect_document": "Informe CPF/CNPJ para o projeto."}
                )

        if status == SpecialProject.STATUS_CLOSED_LOST and not str(loss_reason or "").strip():
            raise serializers.ValidationError(
                {"loss_reason": "Motivo da perda é obrigatório para projeto perdido."}
            )

        return attrs

    def _sync_customer_for_won_project(self, project: SpecialProject):
        if project.status != SpecialProject.STATUS_CLOSED_WON:
            return

        customer = project.customer
        if customer is None:
            email = (project.prospect_email or "").strip().lower()
            customer = Customer.all_objects.filter(
                company=project.company,
                email=email,
            ).first()
            if customer is None:
                digits = "".join(ch for ch in (project.prospect_document or "") if ch.isdigit())
                customer_type = (
                    Customer.TYPE_INDIVIDUAL if len(digits) == 11 else Customer.TYPE_COMPANY
                )
                customer = Customer.all_objects.create(
                    company=project.company,
                    name=(project.prospect_name or "").strip() or f"Projeto {project.id}",
                    email=email or f"projeto-{project.id}@placeholder.local",
                    customer_type=customer_type,
                    lifecycle_stage=Customer.STAGE_CUSTOMER,
                    document=(project.prospect_document or "").strip(),
                    cpf=(project.prospect_document or "").strip() if customer_type == Customer.TYPE_INDIVIDUAL else "",
                    cnpj=(project.prospect_document or "").strip() if customer_type == Customer.TYPE_COMPANY else "",
                    phone=(project.prospect_phone or "").strip(),
                    lead_source=Customer.LEAD_SOURCE_CHOICES[-1][0],
                    industry=Customer.INDUSTRY_CHOICES[-1][0],
                )
            else:
                customer.lifecycle_stage = Customer.STAGE_CUSTOMER
                customer.save(update_fields=("lifecycle_stage", "updated_at"))

            project.customer = customer
            project.save(update_fields=("customer", "updated_at"))
        else:
            customer.lifecycle_stage = Customer.STAGE_CUSTOMER
            customer.save(update_fields=("lifecycle_stage", "updated_at"))

    def create(self, validated_data):
        project = super().create(validated_data)
        self._sync_customer_for_won_project(project)
        return project

    def update(self, instance, validated_data):
        project = super().update(instance, validated_data)
        self._sync_customer_for_won_project(project)
        return project

    class Meta:
        model = SpecialProject
        fields = (
            "id",
            "customer",
            "customer_name",
            "prospect_name",
            "prospect_document",
            "prospect_phone",
            "prospect_email",
            "name",
            "project_type",
            "owner",
            "owner_username",
            "start_date",
            "due_date",
            "swot_strengths",
            "swot_weaknesses",
            "swot_opportunities",
            "swot_threats",
            "status",
            "loss_reason",
            "closed_at",
            "won_at",
            "lost_at",
            "notes",
            "activities",
            "documents",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "customer_name",
            "owner_username",
            "closed_at",
            "won_at",
            "lost_at",
            "activities",
            "documents",
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


class SalesFlowSummarySerializer(serializers.Serializer):
    leads_new = serializers.IntegerField()
    leads_qualified = serializers.IntegerField()
    leads_converted = serializers.IntegerField()
    opportunities_won = serializers.IntegerField()
    winrate = serializers.FloatField()
    pipeline_open = serializers.FloatField()
    activities_open = serializers.IntegerField()
    activities_overdue = serializers.IntegerField()


class AgendaCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    subject = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField(required=False, allow_null=True)
    attendee_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    attendee_email = serializers.EmailField(required=False, allow_blank=True)
    send_invite = serializers.BooleanField(required=False, default=False)
    priority = serializers.ChoiceField(
        choices=CommercialActivity.PRIORITY_CHOICES,
        required=False,
        default=CommercialActivity.PRIORITY_MEDIUM,
    )

    lead = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.none(),
        required=False,
        allow_null=True,
    )
    opportunity = serializers.PrimaryKeyRelatedField(
        queryset=Opportunity.objects.none(),
        required=False,
        allow_null=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=SpecialProject.objects.none(),
        required=False,
        allow_null=True,
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        company = getattr(request, "company", None)
        if company is None:
            return
        self.fields["lead"].queryset = Lead.objects.filter(company=company)
        self.fields["opportunity"].queryset = Opportunity.objects.filter(company=company)
        self.fields["project"].queryset = SpecialProject.objects.filter(company=company)
        self.fields["customer"].queryset = Customer.objects.filter(company=company)

    def validate(self, attrs):
        start_at = attrs["start_at"]
        end_at = attrs.get("end_at")
        if end_at is not None and end_at < start_at:
            raise serializers.ValidationError({"end_at": "end_at must be greater than or equal to start_at."})

        links = {
            "lead": attrs.get("lead"),
            "opportunity": attrs.get("opportunity"),
            "project": attrs.get("project"),
            "customer": attrs.get("customer"),
        }
        active_links = [name for name, value in links.items() if value is not None]
        if len(active_links) != 1:
            raise serializers.ValidationError(
                "Agenda event must be linked to exactly one origin entity: lead, opportunity, project or customer."
            )

        send_invite = attrs.get("send_invite", False)
        attendee_email = (attrs.get("attendee_email") or "").strip()
        if send_invite and not attendee_email:
            raise serializers.ValidationError(
                {"attendee_email": "attendee_email is required when send_invite=true."}
            )
        return attrs


class AgendaEventSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="description", read_only=True)

    class Meta:
        model = CommercialActivity
        fields = (
            "id",
            "title",
            "subject",
            "status",
            "priority",
            "origin",
            "start_at",
            "end_at",
            "remind_at",
            "attendee_name",
            "attendee_email",
            "invite_sent_at",
            "confirmed_at",
            "canceled_at",
            "reminder_state",
            "lead",
            "opportunity",
            "project",
            "customer",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AgendaStatusUpdateSerializer(serializers.Serializer):
    send_email = serializers.BooleanField(required=False, default=False)


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


class TenantAIAssistantRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=4000)
    conversation_id = serializers.IntegerField(required=False, min_value=1)
    focus = serializers.CharField(required=False, allow_blank=True, max_length=255)
    cnpj = serializers.CharField(required=False, allow_blank=True, max_length=18)
    include_cnpj_enrichment = serializers.BooleanField(required=False, default=True)
    include_market_research = serializers.BooleanField(required=False, default=True)
    include_financial_context = serializers.BooleanField(required=False, default=True)
    include_commercial_context = serializers.BooleanField(required=False, default=True)
    learned_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    pin_learning = serializers.BooleanField(required=False, default=False)


class AiConversationSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = AiConversation
        fields = (
            "id",
            "title",
            "status",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AiMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiMessage
        fields = (
            "id",
            "conversation",
            "role",
            "content",
            "intent",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AiConversationDetailSerializer(AiConversationSerializer):
    messages = AiMessageSerializer(many=True, read_only=True)

    class Meta(AiConversationSerializer.Meta):
        fields = AiConversationSerializer.Meta.fields + ("messages",)


class AiConversationMessageRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=4000)


class AiDashboardSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiSuggestion
        fields = (
            "id",
            "scope",
            "title",
            "body",
            "severity",
            "priority",
            "related_entity_type",
            "related_entity_id",
            "created_at",
            "expires_at",
            "seen_at",
        )
        read_only_fields = fields


class TenantDashboardAIInsightsRequestSerializer(serializers.Serializer):
    period_days = serializers.IntegerField(required=False, min_value=7, max_value=365, default=30)
    focus = serializers.CharField(required=False, allow_blank=True, max_length=500)
    weekly_plan = serializers.BooleanField(required=False, default=False)


class TenantAIAssistantInteractionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TenantAIInteraction
        fields = (
            "id",
            "query_text",
            "focus",
            "cnpj",
            "context_snapshot",
            "cnpj_profile",
            "response_payload",
            "learned_note",
            "is_pinned_learning",
            "provider",
            "confidence_score",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "context_snapshot",
            "cnpj_profile",
            "response_payload",
            "provider",
            "confidence_score",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        )


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


class CommissionPlanScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionPlanScope
        fields = (
            "id",
            "priority",
            "insurer_name",
            "product_line",
            "trigger_basis",
            "commission_percent",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class CommissionAccrualSerializer(serializers.ModelSerializer):
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)

    class Meta:
        model = CommissionAccrual
        fields = (
            "id",
            "amount",
            "description",
            "status",
            "recipient",
            "recipient_username",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class CommissionPayoutBatchSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = CommissionPayoutBatch
        fields = (
            "id",
            "status",
            "period_start",
            "period_end",
            "total_amount",
            "created_by",
            "created_by_username",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "total_amount",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        )


class CommissionPayoutBatchCreateSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    producer_id = serializers.IntegerField(required=False, allow_null=True)


class InsurerSettlementBatchSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = InsurerSettlementBatch
        fields = (
            "id",
            "insurer_name",
            "status",
            "period_start",
            "period_end",
            "total_amount",
            "created_by",
            "created_by_username",
            "approved_by",
            "approved_by_username",
            "approved_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "total_amount",
            "created_by",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        )


class InsurerSettlementBatchCreateSerializer(serializers.Serializer):
    insurer_name = serializers.CharField(max_length=120)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
