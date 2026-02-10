from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from customers.models import Company, CompanyMembership
from finance.models import Payable
from operational.models import (
    Apolice,
    CommercialActivity,
    Customer,
    Endosso,
    OperationalIntegrationInbox,
    Installment,
    Lead,
    Opportunity,
)
from commission.models import (
    ParticipantProfile,
    CommissionPlanScope,
    CommissionAccrual,
    CommissionPayoutBatch,
    CommissionPayoutItem,
    InsurerPayableAccrual,
    InsurerSettlementBatch,
)
from tenancy.context import reset_current_company, set_current_company


@override_settings(ALLOWED_HOSTS=["testserver", ".example.com"])
class TenantIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company_a = Company.objects.create(
            name="Empresa A",
            tenant_code="empresa-a",
            subdomain="empresa-a",
        )
        self.company_b = Company.objects.create(
            name="Empresa B",
            tenant_code="empresa-b",
            subdomain="empresa-b",
        )
        self.user_a = User.objects.create_user(
            username="user-a",
            email="usera@empresa-a.com",
            password="strong-pass-a",
        )
        self.user_b = User.objects.create_user(
            username="user-b",
            email="userb@empresa-b.com",
            password="strong-pass-b",
        )
        self.user_manager = User.objects.create_user(
            username="user-manager",
            email="manager@empresa-a.com",
            password="strong-pass-mgr",
        )
        self.user_member = User.objects.create_user(
            username="user-member",
            email="member@empresa-a.com",
            password="strong-pass-member",
        )
        self.user_no_membership = User.objects.create_user(
            username="no-member",
            email="nomember@test.com",
            password="strong-pass-nm",
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.user_a,
            role=CompanyMembership.ROLE_OWNER,
        )
        CompanyMembership.objects.create(
            company=self.company_b,
            user=self.user_b,
            role=CompanyMembership.ROLE_OWNER,
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.user_manager,
            role=CompanyMembership.ROLE_MANAGER,
        )
        CompanyMembership.objects.create(
            company=self.company_a,
            user=self.user_member,
            role=CompanyMembership.ROLE_MEMBER,
        )

        self.customer_a = Customer.all_objects.create(
            company=self.company_a,
            name="Cliente A",
            email="a@cliente.com",
        )
        self.customer_b = Customer.all_objects.create(
            company=self.company_b,
            name="Cliente B",
            email="b@cliente.com",
        )
        self.lead_a = Lead.all_objects.create(
            company=self.company_a,
            source="Website",
            customer=self.customer_a,
            status="NEW",
        )
        self.lead_b = Lead.all_objects.create(
            company=self.company_b,
            source="Referral",
            customer=self.customer_b,
            status="NEW",
        )
        self.opportunity_a = Opportunity.all_objects.create(
            company=self.company_a,
            customer=self.customer_a,
            title="Opp A",
            stage="DISCOVERY",
            amount=1000,
        )
        self.apolice_a = Apolice.all_objects.create(
            company=self.company_a,
            numero="AP-ACME-001",
            seguradora="Seguradora X",
            ramo="Automóvel",
            cliente_nome="Cliente A",
            cliente_cpf_cnpj="00000000000",
            inicio_vigencia=date(2026, 1, 1),
            fim_vigencia=date(2027, 1, 1),
            status="ATIVA",
        )
        self.apolice_b = Apolice.all_objects.create(
            company=self.company_b,
            numero="AP-BETA-001",
            seguradora="Seguradora Y",
            ramo="Vida",
            cliente_nome="Cliente B",
            cliente_cpf_cnpj="11111111111",
            inicio_vigencia=date(2026, 1, 1),
            fim_vigencia=date(2027, 1, 1),
            status="ATIVA",
        )
        self.endosso_a = Endosso.all_objects.create(
            company=self.company_a,
            apolice=self.apolice_a,
            numero_endosso="0",
            tipo="EMISSAO",
            data_emissao=date(2026, 1, 2),
        )
        now = timezone.now()
        self.activity_a = CommercialActivity.all_objects.create(
            company=self.company_a,
            kind=CommercialActivity.KIND_FOLLOW_UP,
            title="Contato inicial",
            status=CommercialActivity.STATUS_PENDING,
            priority=CommercialActivity.PRIORITY_HIGH,
            due_at=now + timedelta(hours=6),
            reminder_at=now - timedelta(minutes=30),
            lead=self.lead_a,
            created_by=self.user_manager,
            sla_hours=8,
        )
        self.activity_a_breached = CommercialActivity.all_objects.create(
            company=self.company_a,
            kind=CommercialActivity.KIND_TASK,
            title="SLA vencido",
            status=CommercialActivity.STATUS_PENDING,
            priority=CommercialActivity.PRIORITY_URGENT,
            due_at=now - timedelta(hours=2),
            reminder_at=now - timedelta(hours=3),
            lead=self.lead_a,
            created_by=self.user_manager,
            sla_due_at=now - timedelta(minutes=10),
        )
        self.activity_b = CommercialActivity.all_objects.create(
            company=self.company_b,
            kind=CommercialActivity.KIND_TASK,
            title="Atividade tenant B",
            status=CommercialActivity.STATUS_PENDING,
            priority=CommercialActivity.PRIORITY_MEDIUM,
            due_at=now + timedelta(days=1),
            lead=self.lead_b,
            created_by=self.user_b,
        )

    def test_header_based_isolation(self):
        self.client.force_login(self.user_a)
        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["email"], "a@cliente.com")

    def test_subdomain_based_isolation(self):
        self.client.force_login(self.user_b)
        response = self.client.get(
            "/api/customers/",
            HTTP_HOST="empresa-b.example.com",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["email"], "b@cliente.com")

    def test_missing_tenant_returns_bad_request(self):
        self.client.force_login(self.user_a)
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_request_is_denied(self):
        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_non_member_user_is_denied(self):
        self.client.force_login(self.user_no_membership)
        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_user_from_other_tenant_is_denied(self):
        self.client.force_login(self.user_b)
        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_token_authentication_flow(self):
        token_response = self.client.post(
            "/api/auth/token/",
            data={"username": "user-a", "password": "strong-pass-a"},
        )
        self.assertEqual(token_response.status_code, 200)
        token = token_response.json().get("token")
        self.assertTrue(token)

        response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
            HTTP_AUTHORIZATION=f"Token {token}",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["email"], "a@cliente.com")

    def test_member_can_read_but_cannot_create_customer(self):
        self.client.force_login(self.user_member)
        read_response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(read_response.status_code, 200)

        write_response = self.client.post(
            "/api/customers/",
            data={
                "name": "Cliente Novo Member",
                "email": "member-write@cliente.com",
                "phone": "",
                "document": "",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(write_response.status_code, 403)

    def test_manager_can_create_customer(self):
        self.client.force_login(self.user_manager)
        write_response = self.client.post(
            "/api/customers/",
            data={
                "name": "Cliente Novo Manager",
                "email": "manager-write@cliente.com",
                "phone": "",
                "document": "",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(write_response.status_code, 201)
        self.assertEqual(write_response.json()["email"], "manager-write@cliente.com")

        read_response = self.client.get(
            "/api/customers/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        emails = [item["email"] for item in read_response.json()]
        self.assertIn("manager-write@cliente.com", emails)

    def test_manager_cannot_delete_customer(self):
        self.client.force_login(self.user_manager)
        response = self.client.delete(
            f"/api/customers/{self.customer_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_can_delete_customer(self):
        self.client.force_login(self.user_a)
        response = self.client.delete(
            f"/api/customers/{self.customer_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 204)

    def test_member_can_read_leads_but_cannot_create(self):
        self.client.force_login(self.user_member)
        read_response = self.client.get(
            "/api/leads/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(len(read_response.json()), 1)
        self.assertEqual(read_response.json()[0]["id"], self.lead_a.id)

        write_response = self.client.post(
            "/api/leads/",
            data={
                "source": "Member source",
                "customer": self.customer_a.id,
                "status": "NEW",
                "notes": "should fail",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(write_response.status_code, 403)

    def test_manager_can_create_and_update_lead_but_cannot_delete(self):
        self.client.force_login(self.user_manager)
        create_response = self.client.post(
            "/api/leads/",
            data={
                "source": "Manager source",
                "customer": self.customer_a.id,
                "status": "NEW",
                "notes": "created",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 201)
        lead_id = create_response.json()["id"]

        patch_response = self.client.patch(
            f"/api/leads/{lead_id}/",
            data={"status": "QUALIFIED"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["status"], "QUALIFIED")

        delete_response = self.client.delete(
            f"/api/leads/{lead_id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(delete_response.status_code, 403)

    def test_owner_can_delete_lead(self):
        self.client.force_login(self.user_a)
        response = self.client.delete(
            f"/api/leads/{self.lead_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 204)

    def test_manager_can_create_opportunity_but_cannot_delete(self):
        self.client.force_login(self.user_manager)
        create_response = self.client.post(
            "/api/opportunities/",
            data={
                "customer": self.customer_a.id,
                "title": "Opp Manager",
                "stage": "DISCOVERY",
                "amount": "1500.00",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 201)
        opportunity_id = create_response.json()["id"]

        delete_response = self.client.delete(
            f"/api/opportunities/{opportunity_id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(delete_response.status_code, 403)

    def test_owner_can_delete_opportunity(self):
        self.client.force_login(self.user_a)
        response = self.client.delete(
            f"/api/opportunities/{self.opportunity_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 204)

    def test_cross_tenant_customer_reference_is_rejected(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/opportunities/",
            data={
                "customer": self.customer_b.id,
                "title": "Cross tenant opp",
                "stage": "DISCOVERY",
                "amount": "1000.00",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_apolices_are_isolated_by_tenant(self):
        self.client.force_login(self.user_a)
        response = self.client.get(
            "/api/apolices/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["numero"], "AP-ACME-001")

    def test_manager_cannot_create_apolice(self):
        self.client.force_login(self.user_manager)
        create_response = self.client.post(
            "/api/apolices/",
            data={
                "numero": "AP-ACME-002",
                "seguradora": "Seguradora Z",
                "ramo": "Residencial",
                "cliente_nome": "Cliente Novo",
                "cliente_cpf_cnpj": "22222222222",
                "inicio_vigencia": "2026-03-01",
                "fim_vigencia": "2027-03-01",
                "status": "ATIVA",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 403)

    def test_owner_can_create_and_delete_apolice(self):
        self.client.force_login(self.user_a)
        create_response = self.client.post(
            "/api/apolices/",
            data={
                "numero": "AP-ACME-003",
                "seguradora": "Seguradora Owner",
                "ramo": "Empresarial",
                "cliente_nome": "Cliente Owner",
                "cliente_cpf_cnpj": "33333333333",
                "inicio_vigencia": "2026-04-01",
                "fim_vigencia": "2027-04-01",
                "status": "ATIVA",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 201)
        apolice_id = create_response.json()["id"]

        delete_response = self.client.delete(
            f"/api/apolices/{apolice_id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_company_override_can_allow_manager_create_apolice(self):
        self.company_a.rbac_overrides = {"apolices": {"POST": ["OWNER", "MANAGER"]}}
        self.company_a.save(update_fields=["rbac_overrides"])

        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/apolices/",
            data={
                "numero": "AP-ACME-004",
                "seguradora": "Seguradora Override",
                "ramo": "Empresarial",
                "cliente_nome": "Cliente Override",
                "cliente_cpf_cnpj": "44444444444",
                "inicio_vigencia": "2026-05-01",
                "fim_vigencia": "2027-05-01",
                "status": "ATIVA",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 201)

    def test_owner_can_delete_apolice(self):
        self.client.force_login(self.user_a)
        response = self.client.delete(
            f"/api/apolices/{self.apolice_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 204)

    def test_endosso_cross_tenant_apolice_is_rejected(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            "/api/endossos/",
            data={
                "apolice": self.apolice_b.id,
                "numero_endosso": "1",
                "tipo": "INCLUSAO",
                "data_emissao": "2026-02-01",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_create_endosso(self):
        self.client.force_login(self.user_manager)
        create_response = self.client.post(
            "/api/endossos/",
            data={
                "apolice": self.apolice_a.id,
                "numero_endosso": "1",
                "tipo": "INCLUSAO",
                "data_emissao": "2026-02-01",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 403)

    def test_owner_can_create_and_delete_endosso(self):
        self.client.force_login(self.user_a)
        create_response = self.client.post(
            "/api/endossos/",
            data={
                "apolice": self.apolice_a.id,
                "numero_endosso": "2",
                "tipo": "INCLUSAO",
                "data_emissao": "2026-02-10",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 201)
        endosso_id = create_response.json()["id"]

        delete_response = self.client.delete(
            f"/api/endossos/{endosso_id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_company_override_can_allow_manager_create_endosso(self):
        self.company_a.rbac_overrides = {"endossos": {"POST": ["OWNER", "MANAGER"]}}
        self.company_a.save(update_fields=["rbac_overrides"])

        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/endossos/",
            data={
                "apolice": self.apolice_a.id,
                "numero_endosso": "3",
                "tipo": "INCLUSAO",
                "data_emissao": "2026-02-11",
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 201)

    def test_owner_can_delete_endosso(self):
        self.client.force_login(self.user_a)
        response = self.client.delete(
            f"/api/endossos/{self.endosso_a.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 204)

    def test_manager_fails_closed_without_tenant_context(self):
        self.assertEqual(Customer.objects.count(), 0)

    def test_manager_filters_with_current_tenant(self):
        token = set_current_company(self.company_a)
        try:
            self.assertEqual(Customer.objects.count(), 1)
            self.assertEqual(Customer.objects.first().email, "a@cliente.com")
        finally:
            reset_current_company(token)

    def test_manager_can_qualify_lead_action(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/qualify/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "QUALIFIED")

    def test_member_cannot_qualify_lead_action(self):
        self.client.force_login(self.user_member)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/qualify/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_convert_requires_qualified_lead(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/convert/",
            data={"title": "Opp from lead"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_can_convert_qualified_lead(self):
        self.lead_a.status = "QUALIFIED"
        self.lead_a.save(update_fields=["status", "updated_at"])

        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/convert/",
            data={
                "title": "Opp converted",
                "amount": "3500.00",
                "stage": "DISCOVERY",
            },
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["lead"]["status"], "CONVERTED")
        self.assertEqual(payload["opportunity"]["title"], "Opp converted")
        self.assertEqual(payload["opportunity"]["source_lead"], self.lead_a.id)

    def test_convert_lead_without_customer_requires_payload_customer(self):
        lead = Lead.all_objects.create(
            company=self.company_a,
            source="Inbound",
            customer=None,
            status="QUALIFIED",
        )
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{lead.id}/convert/",
            data={"title": "No customer convert"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_convert_qualified_lead_auto_creates_customer_from_lead(self):
        lead = Lead.all_objects.create(
            company=self.company_a,
            source="Inbound LP",
            customer=None,
            status="QUALIFIED",
            full_name="Carla Lima",
            company_name="Lima Transportes LTDA",
            email="contato@limatransportes.com",
            phone="11999990000",
            cnpj="12888877000190",
            products_of_interest="Seguro frota",
            notes="Lead com intenção de fechamento em 15 dias.",
        )
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{lead.id}/convert/",
            data={
                "title": "Oportunidade auto-criada",
                "amount": "9800.00",
            },
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["customer_created"])
        self.assertEqual(payload["customer"]["email"], "contato@limatransportes.com")
        self.assertEqual(payload["customer"]["cnpj"], "12888877000190")
        self.assertEqual(payload["lead"]["status"], "CONVERTED")
        self.assertEqual(payload["opportunity"]["source_lead"], lead.id)

    def test_convert_lead_rejects_cross_tenant_customer(self):
        lead = Lead.all_objects.create(
            company=self.company_a,
            source="Inbound",
            customer=None,
            status="QUALIFIED",
        )
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{lead.id}/convert/",
            data={
                "title": "Cross tenant customer",
                "customer": self.customer_b.id,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_opportunity_stage_update_accepts_valid_transition(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/opportunities/{self.opportunity_a.id}/stage/",
            data={"stage": "PROPOSAL"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "PROPOSAL")

    def test_opportunity_stage_update_rejects_invalid_transition(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/opportunities/{self.opportunity_a.id}/stage/",
            data={"stage": "WON"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_opportunity_stage_update_member_forbidden(self):
        self.client.force_login(self.user_member)
        response = self.client.post(
            f"/api/opportunities/{self.opportunity_a.id}/stage/",
            data={"stage": "PROPOSAL"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_opportunity_stage_update_isolated_by_tenant(self):
        foreign_opportunity = Opportunity.all_objects.create(
            company=self.company_b,
            customer=self.customer_b,
            title="Opp B",
            stage="DISCOVERY",
            amount=2000,
        )
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/opportunities/{foreign_opportunity.id}/stage/",
            data={"stage": "PROPOSAL"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 404)

    def test_member_can_read_activities_but_cannot_create(self):
        self.client.force_login(self.user_member)
        list_response = self.client.get(
            "/api/activities/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(list_response.status_code, 200)
        returned_ids = {row["id"] for row in list_response.json()}
        self.assertIn(self.activity_a.id, returned_ids)
        self.assertNotIn(self.activity_b.id, returned_ids)

        create_response = self.client.post(
            "/api/activities/",
            data={
                "kind": "FOLLOW_UP",
                "title": "Follow-up member",
                "lead": self.lead_a.id,
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(create_response.status_code, 403)

    def test_manager_can_create_activity_for_lead(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/activities/",
            data={
                "kind": "TASK",
                "title": "Enviar proposta",
                "description": "Enviar proposta em PDF",
                "priority": "HIGH",
                "lead": self.lead_a.id,
                "sla_hours": 24,
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["lead"], self.lead_a.id)
        self.assertEqual(payload["opportunity"], None)
        self.assertIsNotNone(payload["sla_due_at"])

    def test_manager_cannot_create_activity_with_cross_tenant_lead(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            "/api/activities/",
            data={
                "kind": "TASK",
                "title": "Cross tenant activity",
                "lead": self.lead_b.id,
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_can_complete_and_reopen_activity(self):
        self.client.force_login(self.user_manager)
        complete_response = self.client.post(
            f"/api/activities/{self.activity_a.id}/complete/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["status"], "DONE")
        self.assertIsNotNone(complete_response.json()["completed_at"])

        reopen_response = self.client.post(
            f"/api/activities/{self.activity_a.id}/reopen/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(reopen_response.status_code, 200)
        self.assertEqual(reopen_response.json()["status"], "PENDING")
        self.assertIsNone(reopen_response.json()["completed_at"])

    def test_member_cannot_complete_activity(self):
        self.client.force_login(self.user_member)
        response = self.client.post(
            f"/api/activities/{self.activity_a.id}/complete/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    def test_activity_detail_is_isolated_by_tenant(self):
        self.client.force_login(self.user_manager)
        response = self.client.get(
            f"/api/activities/{self.activity_b.id}/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 404)

    def test_reminders_endpoint_returns_due_unsent_only_from_tenant(self):
        self.client.force_login(self.user_manager)
        response = self.client.get(
            "/api/activities/reminders/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.json()}
        self.assertIn(self.activity_a.id, returned_ids)
        self.assertIn(self.activity_a_breached.id, returned_ids)
        self.assertNotIn(self.activity_b.id, returned_ids)

    def test_manager_can_mark_activity_reminded(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/activities/{self.activity_a.id}/mark-reminded/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["reminder_sent"])

    def test_lead_history_returns_activities_and_converted_opportunities(self):
        Opportunity.all_objects.create(
            company=self.company_a,
            customer=self.customer_a,
            source_lead=self.lead_a,
            title="Opp from lead A",
            stage="DISCOVERY",
            amount=1800,
        )
        self.client.force_login(self.user_manager)
        response = self.client.get(
            f"/api/leads/{self.lead_a.id}/history/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lead"]["id"], self.lead_a.id)
        self.assertGreaterEqual(len(payload["activities"]), 1)
        self.assertGreaterEqual(len(payload["converted_opportunities"]), 1)

    def test_opportunity_history_returns_related_activities(self):
        activity = CommercialActivity.all_objects.create(
            company=self.company_a,
            kind=CommercialActivity.KIND_NOTE,
            title="Nota da oportunidade",
            opportunity=self.opportunity_a,
            created_by=self.user_manager,
        )
        self.client.force_login(self.user_manager)
        response = self.client.get(
            f"/api/opportunities/{self.opportunity_a.id}/history/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        returned_ids = {item["id"] for item in payload["activities"]}
        self.assertIn(activity.id, returned_ids)

    def test_manager_can_generate_lead_ai_insights(self):
        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/ai-insights/",
            data={"focus": "estratégia de fechamento"},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["entity_type"], "LEAD")
        self.assertEqual(payload["entity_id"], self.lead_a.id)
        self.assertIn("insights", payload)
        self.assertIn("summary", payload["insights"])
        self.lead_a.refresh_from_db()
        self.assertIn("latest", self.lead_a.ai_insights)

    def test_member_cannot_generate_lead_ai_insights(self):
        self.client.force_login(self.user_member)
        response = self.client.post(
            f"/api/leads/{self.lead_a.id}/ai-insights/",
            data={},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 403)

    @patch("operational.views.lookup_cnpj_profile")
    def test_lead_cnpj_enrichment_endpoint_updates_lead(self, lookup_mock):
        lead = Lead.all_objects.create(
            company=self.company_a,
            source="CNPJ source",
            status="NEW",
            cnpj="12888877000190",
        )
        lookup_mock.return_value = {
            "success": True,
            "provider": "cnpj_lookup",
            "cnpj": "12888877000190",
            "payload": {
                "razao_social": "Empresa Exemplo LTDA",
                "nome_fantasia": "Exemplo",
                "uf": "SP",
                "municipio": "São Paulo",
                "qsa": [{"nome_socio": "Fulano de Tal"}],
            },
        }

        self.client.force_login(self.user_manager)
        response = self.client.post(
            f"/api/leads/{lead.id}/ai-enrich-cnpj/",
            data={},
            content_type="application/json",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.company_name, "Empresa Exemplo LTDA")
        self.assertIn("Sócios identificados", lead.notes)

    def test_metrics_endpoint_returns_funnel_and_activity_kpis(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/sales/metrics/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], self.company_a.tenant_code)
        self.assertIn("lead_funnel", payload)
        self.assertIn("opportunity_funnel", payload)
        self.assertIn("activities", payload)
        self.assertIn("activities_by_priority", payload)
        self.assertIn("pipeline_value", payload)
        self.assertIn("period", payload)
        self.assertIn("conversion", payload)
        self.assertGreaterEqual(payload["activities"]["open_total"], 1)
        self.assertGreaterEqual(payload["activities"]["sla_breached_total"], 1)

    def test_metrics_endpoint_supports_filters_and_pipeline_values(self):
        old_lead = Lead.all_objects.create(
            company=self.company_a,
            source="Old campaign",
            customer=self.customer_a,
            status="CONVERTED",
        )
        old_opportunity = Opportunity.all_objects.create(
            company=self.company_a,
            customer=self.customer_a,
            title="Old Won",
            stage="WON",
            amount=9000,
            expected_close_date=timezone.localdate() - timedelta(days=40),
        )
        historical_timestamp = timezone.now() - timedelta(days=60)
        Lead.all_objects.filter(pk=old_lead.pk).update(created_at=historical_timestamp)
        Opportunity.all_objects.filter(pk=old_opportunity.pk).update(
            created_at=historical_timestamp
        )

        Opportunity.all_objects.create(
            company=self.company_a,
            customer=self.customer_a,
            title="Close soon",
            stage="PROPOSAL",
            amount=3200,
            expected_close_date=timezone.localdate() + timedelta(days=10),
        )
        CommercialActivity.all_objects.create(
            company=self.company_a,
            kind=CommercialActivity.KIND_TASK,
            title="Manager assigned",
            status=CommercialActivity.STATUS_PENDING,
            priority=CommercialActivity.PRIORITY_HIGH,
            due_at=timezone.now() + timedelta(days=1),
            lead=self.lead_a,
            assigned_to=self.user_manager,
            created_by=self.user_manager,
        )
        CommercialActivity.all_objects.create(
            company=self.company_a,
            kind=CommercialActivity.KIND_TASK,
            title="Member assigned",
            status=CommercialActivity.STATUS_PENDING,
            priority=CommercialActivity.PRIORITY_MEDIUM,
            due_at=timezone.now() + timedelta(days=1),
            lead=self.lead_a,
            assigned_to=self.user_member,
            created_by=self.user_manager,
        )

        from_date = (timezone.localdate() - timedelta(days=30)).isoformat()
        to_date = timezone.localdate().isoformat()

        self.client.force_login(self.user_member)
        response = self.client.get(
            f"/api/sales/metrics/?from={from_date}&to={to_date}&assigned_to={self.user_manager.id}",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["period"]["from_date"], from_date)
        self.assertEqual(payload["period"]["to_date"], to_date)
        self.assertEqual(payload["period"]["assigned_to_user_id"], self.user_manager.id)
        self.assertEqual(payload["activities"]["open_total"], 1)
        self.assertEqual(payload["activities_by_priority"]["HIGH"], 1)
        self.assertEqual(payload["activities_by_priority"]["MEDIUM"], 0)
        self.assertAlmostEqual(payload["pipeline_value"]["open_total_amount"], 4200.0, places=2)
        self.assertAlmostEqual(
            payload["pipeline_value"]["expected_close_next_30d_amount"],
            3200.0,
            places=2,
        )
        self.assertAlmostEqual(payload["pipeline_value"]["won_total_amount"], 0.0, places=2)

    def test_metrics_endpoint_rejects_invalid_date_range(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/sales/metrics/?from=2026-12-31&to=2026-01-01",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("from", response.json()["detail"])

    def test_metrics_endpoint_rejects_invalid_assigned_to(self):
        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/sales/metrics/?assigned_to=abc",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("assigned_to", response.json()["detail"])

    def test_dashboard_summary_is_isolated_and_includes_financial_kpis(self):
        today = timezone.localdate()

        Endosso.all_objects.create(
            company=self.company_a,
            apolice=self.apolice_a,
            numero_endosso="99",
            tipo="EMISSAO",
            premio_total="1000.00",
            valor_comissao="120.00",
            data_emissao=today,
        )
        Endosso.all_objects.create(
            company=self.company_b,
            apolice=self.apolice_b,
            numero_endosso="99",
            tipo="EMISSAO",
            premio_total="777.00",
            valor_comissao="77.00",
            data_emissao=today,
        )

        self.client.force_login(self.user_member)
        response = self.client.get(
            "/api/dashboard/summary/",
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["tenant_code"], self.company_a.tenant_code)
        self.assertAlmostEqual(payload["kpis"]["production_premium_mtd"], 1000.0, places=2)
        self.assertAlmostEqual(payload["kpis"]["commission_mtd"], 120.0, places=2)

    def test_sales_goals_permissions(self):
        today = timezone.localdate()

        self.client.force_login(self.user_member)
        member_response = self.client.post(
            "/api/sales-goals/",
            data={
                "year": today.year,
                "month": today.month,
                "premium_goal": "5000.00",
                "commission_goal": "800.00",
                "new_customers_goal": 10,
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(member_response.status_code, 403)

        self.client.force_login(self.user_manager)
        manager_response = self.client.post(
            "/api/sales-goals/",
            data={
                "year": today.year,
                "month": today.month,
                "premium_goal": "5000.00",
                "commission_goal": "800.00",
                "new_customers_goal": 10,
            },
            HTTP_X_TENANT_ID=self.company_a.tenant_code,
        )
        self.assertEqual(manager_response.status_code, 201)


class AccrualServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Accrual Corp", tenant_code="accrual", subdomain="accrual"
        )
        self.apolice = Apolice.all_objects.create(
            company=self.company,
            numero="AP-001",
            seguradora="Seguradora A",
            ramo="Auto",
            cliente_nome="Cliente Teste",
            cliente_cpf_cnpj="000",
            inicio_vigencia=date(2026, 1, 1),
            fim_vigencia=date(2027, 1, 1),
        )
        self.endosso = Endosso.all_objects.create(
            company=self.company,
            apolice=self.apolice,
            numero_endosso="0",
            tipo="EMISSAO",
            premio_liquido="1000.00",
            data_emissao=date(2026, 1, 1),
        )
        self.installment = Installment.all_objects.create(
            company=self.company,
            endosso=self.endosso,
            number=1,
            amount="500.00",
            due_date=date(2026, 2, 1),
        )

    def test_accrue_on_policy_issued_respects_priority_and_basis(self):
        from operational.services import accrue_on_policy_issued

        # Plan 1: Low priority, matches everything
        CommissionPlanScope.all_objects.create(
            company=self.company,
            priority=10,
            commission_percent="10.00",
            trigger_basis="ISSUED",
        )
        # Plan 2: High priority, matches specific insurer
        CommissionPlanScope.all_objects.create(
            company=self.company,
            priority=100,
            insurer_name="Seguradora A",
            commission_percent="20.00",
            trigger_basis="ISSUED",
        )

        event = {"id": "evt_1", "data": {"endosso_id": self.endosso.id}}
        accrue_on_policy_issued(event, self.company)

        accrual = CommissionAccrual.objects.get(company=self.company)
        # Should match Plan 2 (20% of 1000 = 200)
        self.assertEqual(accrual.amount, 200.00)
        self.assertEqual(accrual.content_object, self.endosso)

        payable = InsurerPayableAccrual.objects.get(company=self.company)
        self.assertEqual(payable.amount, 200.00)
        self.assertEqual(payable.insurer_name, "Seguradora A")

    def test_accrue_on_policy_issued_ignores_paid_basis_plans(self):
        from operational.services import accrue_on_policy_issued

        CommissionPlanScope.all_objects.create(
            company=self.company,
            priority=100,
            commission_percent="20.00",
            trigger_basis="PAID",
        )

        event = {"id": "evt_2", "data": {"endosso_id": self.endosso.id}}
        accrue_on_policy_issued(event, self.company)

        self.assertFalse(CommissionAccrual.objects.exists())

    def test_accrue_on_installment_paid_respects_basis(self):
        from operational.services import accrue_on_installment_paid

        CommissionPlanScope.all_objects.create(
            company=self.company,
            priority=100,
            commission_percent="15.00",
            trigger_basis="PAID",
        )

        event = {"id": "evt_3", "data": {"installment_id": self.installment.id}}
        accrue_on_installment_paid(event, self.company)

        accrual = CommissionAccrual.objects.get(company=self.company)
        # 15% of 500 = 75
        self.assertEqual(accrual.amount, 75.00)
        self.assertEqual(accrual.content_object, self.installment)

    def test_idempotency_prevents_double_accrual(self):
        from operational.services import accrue_on_policy_issued

        CommissionPlanScope.all_objects.create(
            company=self.company,
            priority=100,
            commission_percent="10.00",
            trigger_basis="ISSUED",
        )

        event = {"id": "evt_duplicate", "data": {"endosso_id": self.endosso.id}}
        
        # First call
        accrue_on_policy_issued(event, self.company)
        self.assertEqual(CommissionAccrual.objects.count(), 1)
        self.assertEqual(OperationalIntegrationInbox.objects.count(), 1)

        # Second call with same event ID
        accrue_on_policy_issued(event, self.company)
        self.assertEqual(CommissionAccrual.objects.count(), 1)

        # Different event ID
        event["id"] = "evt_new"
        accrue_on_policy_issued(event, self.company)
        self.assertEqual(CommissionAccrual.objects.count(), 2)

    def test_apply_endorsement_delta_creates_adjustment(self):
        from operational.services import apply_endorsement_delta
        from django.contrib.contenttypes.models import ContentType

        # Initial accrual
        ct = ContentType.objects.get_for_model(Endosso)
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ct,
            object_id=self.endosso.id,
            amount=Decimal("100.00"),
            status=CommissionAccrual.STATUS_PAYABLE
        )

        # Update endorsement commission to 150 (Delta +50)
        self.endosso.valor_comissao = Decimal("150.00")
        self.endosso.save()

        event = {"data": {"endosso_id": self.endosso.id}}
        apply_endorsement_delta(event, self.company)

        self.assertEqual(CommissionAccrual.objects.count(), 2)
        delta_accrual = CommissionAccrual.objects.latest("created_at")
        self.assertEqual(delta_accrual.amount, Decimal("50.00"))

    def test_apply_endorsement_delta_creates_negative_adjustment(self):
        from operational.services import apply_endorsement_delta
        from django.contrib.contenttypes.models import ContentType

        # Initial accrual 100
        ct = ContentType.objects.get_for_model(Endosso)
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ct,
            object_id=self.endosso.id,
            amount=Decimal("100.00"),
            status=CommissionAccrual.STATUS_PAYABLE
        )

        # Update endorsement commission to 80 (Delta -20)
        self.endosso.valor_comissao = Decimal("80.00")
        self.endosso.save()

        event = {"data": {"endosso_id": self.endosso.id}}
        apply_endorsement_delta(event, self.company)

        delta_accrual = CommissionAccrual.objects.latest("created_at")
        self.assertEqual(delta_accrual.amount, Decimal("-20.00"))

    def test_create_commission_payout_batch(self):
        from operational.services import create_commission_payout_batch
        
        # Create 2 payable accruals
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Endosso),
            object_id=self.endosso.id,
            amount=Decimal("100.00"),
            status=CommissionAccrual.STATUS_PAYABLE
        )
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Endosso),
            object_id=self.endosso.id,
            amount=Decimal("50.00"),
            status=CommissionAccrual.STATUS_PAYABLE
        )

        today = date.today()
        batch = create_commission_payout_batch(
            self.company, 
            period_from=today - timedelta(days=1), 
            period_to=today + timedelta(days=1),
            created_by=self.user_manager # Assuming user_manager exists in this context or mock
        )

        self.assertIsNotNone(batch)
        self.assertEqual(batch.total_amount, Decimal("150.00"))
        self.assertEqual(batch.items.count(), 2)
        
        # Ensure idempotency (items already in batch shouldn't be picked up again)
        batch2 = create_commission_payout_batch(self.company, today, today, created_by=self.user_manager)
        self.assertIsNone(batch2)


class PayoutProcessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Payout Corp", tenant_code="payout", subdomain="payout")
        self.maker = User.objects.create_user(username="maker", email="maker@payout.com")
        self.checker = User.objects.create_user(username="checker", email="checker@payout.com")
        self.producer = User.objects.create_user(username="producer", email="prod@payout.com")
        self.employee = User.objects.create_user(username="employee", email="emp@payout.com")
        
        # Profiles
        ParticipantProfile.objects.create(
            company=self.company,
            user=self.producer,
            participant_type=ParticipantProfile.TYPE_INDEPENDENT
        )
        ParticipantProfile.objects.create(
            company=self.company,
            user=self.employee,
            participant_type=ParticipantProfile.TYPE_EMPLOYEE
        )
        
        # Create accrual
        self.accrual = CommissionAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Company), # Dummy CT
            object_id=self.company.id,
            amount=Decimal("500.00"),
            status=CommissionAccrual.STATUS_PAYABLE,
            recipient=self.producer,
            recipient_type=ParticipantProfile.TYPE_INDEPENDENT
        )

    def test_approve_batch_enforces_sod(self):
        from operational.services import create_commission_payout_batch, approve_commission_payout_batch

        today = date.today()
        batch = create_commission_payout_batch(
            self.company, today, today, created_by=self.maker
        )

        # Maker tries to approve own batch -> Fail
        with self.assertRaises(PermissionDenied):
            approve_commission_payout_batch(batch.id, self.maker, self.company)

        # Checker approves -> Success
        approve_commission_payout_batch(batch.id, self.checker, self.company)
        batch.refresh_from_db()
        self.assertEqual(batch.status, CommissionPayoutBatch.STATUS_APPROVED)
        self.assertEqual(batch.approved_by, self.checker)

    def test_generate_payables_creates_finance_records(self):
        from operational.services import (
            create_commission_payout_batch, 
            approve_commission_payout_batch,
            generate_payables_for_payout_batch,
            confirm_commission_payout
        )

        today = date.today()
        # Create another accrual for same producer to test aggregation
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Company),
            object_id=self.company.id,
            amount=Decimal("250.00"),
            status=CommissionAccrual.STATUS_PAYABLE,
            recipient=self.producer
        )

        batch = create_commission_payout_batch(
            self.company, today, today, created_by=self.maker
        )
        approve_commission_payout_batch(batch.id, self.checker, self.company)

        generate_payables_for_payout_batch(batch.id, self.company)

        batch.refresh_from_db()
        self.assertEqual(batch.status, CommissionPayoutBatch.STATUS_PROCESSED)

        # Check Payables
        payables = Payable.objects.filter(company=self.company)
        self.assertEqual(payables.count(), 1) # Aggregated by producer
        payable = payables.first()
        self.assertEqual(payable.amount, Decimal("750.00"))
        self.assertEqual(payable.recipient, self.producer)
        self.assertEqual(payable.source_ref, str(batch.id))

        # Accruals should NOT be PAID yet
        self.accrual.refresh_from_db()
        self.assertEqual(self.accrual.status, CommissionAccrual.STATUS_PAYABLE)

        # Confirm Payment
        event = {"id": "evt_pay_1", "data": {"batch_id": batch.id}}
        confirm_commission_payout(event, self.company)

        batch.refresh_from_db()
        self.assertEqual(batch.status, CommissionPayoutBatch.STATUS_PAID)
        
        self.accrual.refresh_from_db()
        self.assertEqual(self.accrual.status, CommissionAccrual.STATUS_PAID)

    def test_generate_payables_requires_approved_status(self):
        from operational.services import create_commission_payout_batch, generate_payables_for_payout_batch
        
        batch = create_commission_payout_batch(self.company, date.today(), date.today(), created_by=self.maker)
        with self.assertRaises(ValidationError):
            generate_payables_for_payout_batch(batch.id, self.company)

    def test_payout_batch_applies_retention_rule(self):
        from operational.services import create_commission_payout_batch
        
        # Update producer profile with retention
        profile = self.producer.commission_profile
        profile.payout_rules = {"retention_percent": 10.0}
        profile.save()
        
        today = date.today()
        batch = create_commission_payout_batch(
            self.company, today, today, created_by=self.maker
        )
        
        self.assertEqual(batch.items.count(), 1)
        item = batch.items.first()
        # 500.00 - 10% = 450.00
        self.assertEqual(item.amount, Decimal("450.00"))
        self.assertEqual(batch.total_amount, Decimal("450.00"))

    def test_payout_batch_filters_by_participant_type(self):
        from operational.services import create_commission_payout_batch
        
        # Create employee accrual
        CommissionAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Company),
            object_id=self.company.id,
            amount=Decimal("300.00"),
            status=CommissionAccrual.STATUS_PAYABLE,
            recipient=self.employee,
            recipient_type=ParticipantProfile.TYPE_EMPLOYEE
        )
        
        today = date.today()
        
        # Batch for Employees only
        batch_emp = create_commission_payout_batch(
            self.company, today, today, created_by=self.maker, participant_type=ParticipantProfile.TYPE_EMPLOYEE
        )
        self.assertEqual(batch_emp.items.count(), 1)
        self.assertEqual(batch_emp.items.first().accrual.recipient, self.employee)
        
        # Batch for Independent only (should pick up the producer accrual from setUp)
        batch_ind = create_commission_payout_batch(
            self.company, today, today, created_by=self.maker, participant_type=ParticipantProfile.TYPE_INDEPENDENT
        )
        self.assertEqual(batch_ind.items.count(), 1)
        self.assertEqual(batch_ind.items.first().accrual.recipient, self.producer)


class InsurerSettlementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Insurer Corp", tenant_code="insurer", subdomain="insurer")
        self.maker = User.objects.create_user(username="maker_ins", email="maker@insurer.com")
        self.checker = User.objects.create_user(username="checker_ins", email="checker@insurer.com")
        
        # Create insurer payable
        self.payable = InsurerPayableAccrual.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Company),
            object_id=self.company.id,
            amount=Decimal("1000.00"),
            insurer_name="Seguradora Top",
            status=InsurerPayableAccrual.STATUS_PENDING
        )

    def test_full_settlement_flow(self):
        from operational.services import (
            create_insurer_settlement_batch,
            approve_insurer_settlement_batch,
            generate_payables_for_insurer_settlement,
            confirm_insurer_settlement
        )

        today = date.today()
        
        # 1. Create Batch
        batch = create_insurer_settlement_batch(
            self.company, "Seguradora Top", today, today, self.maker
        )
        self.assertIsNotNone(batch)
        self.assertEqual(batch.total_amount, Decimal("1000.00"))

        # 2. Approve Batch (SoD)
        with self.assertRaises(PermissionDenied):
            approve_insurer_settlement_batch(batch.id, self.maker, self.company)
        
        approve_insurer_settlement_batch(batch.id, self.checker, self.company)
        batch.refresh_from_db()
        self.assertEqual(batch.status, InsurerSettlementBatch.STATUS_APPROVED)

        # 3. Generate Payables
        generate_payables_for_insurer_settlement(batch.id, self.company)
        
        batch.refresh_from_db()
        self.assertEqual(batch.status, InsurerSettlementBatch.STATUS_PROCESSED)
        
        # Not settled yet
        self.payable.refresh_from_db()
        self.assertEqual(self.payable.status, InsurerPayableAccrual.STATUS_PENDING)
        
        finance_payable = Payable.objects.get(company=self.company)
        self.assertEqual(finance_payable.beneficiary_name, "Seguradora Top")
        self.assertEqual(finance_payable.amount, Decimal("1000.00"))

        # 4. Confirm Settlement
        event = {"id": "evt_ins_pay_1", "data": {"batch_id": batch.id}}
        confirm_insurer_settlement(event, self.company)

        self.payable.refresh_from_db()
        self.assertEqual(self.payable.status, InsurerPayableAccrual.STATUS_SETTLED)
