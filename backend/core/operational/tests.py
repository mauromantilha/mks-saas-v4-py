from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from customers.models import Company, CompanyMembership
from operational.models import Apolice, Customer, Endosso, Lead, Opportunity
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
