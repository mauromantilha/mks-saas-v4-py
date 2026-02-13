from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from customers.models import Company, CompanyMembership
from operational.models import CommercialActivity, Customer, Lead, Opportunity

User = get_user_model()


class SalesFlowAgendaApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="sales-owner",
            email="owner@sales.test",
            password="testpass123",
        )
        self.manager = User.objects.create_user(
            username="sales-manager",
            email="manager@sales.test",
            password="testpass123",
        )
        self.member = User.objects.create_user(
            username="sales-member",
            email="member@sales.test",
            password="testpass123",
        )

        self.company = Company.objects.create(
            name="Sales Company",
            tenant_code="sales-company",
            subdomain="sales-company",
            is_active=True,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.owner,
            role=CompanyMembership.ROLE_OWNER,
            is_active=True,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.manager,
            role=CompanyMembership.ROLE_MANAGER,
            is_active=True,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.member,
            role=CompanyMembership.ROLE_MEMBER,
            is_active=True,
        )

        self.customer = Customer.objects.create(
            company=self.company,
            name="Customer Sales",
            email="customer@sales.test",
        )
        self.lead_new = Lead.objects.create(
            company=self.company,
            source="Website",
            status="NEW",
            full_name="Lead New",
        )
        self.lead_qualified = Lead.objects.create(
            company=self.company,
            source="Website",
            status="QUALIFIED",
            full_name="Lead Qualified",
        )
        self.lead_converted = Lead.objects.create(
            company=self.company,
            source="Website",
            status="CONVERTED",
            full_name="Lead Converted",
        )

        self.opportunity_won = Opportunity.objects.create(
            company=self.company,
            customer=self.customer,
            source_lead=self.lead_converted,
            title="Won Opp",
            stage="WON",
            amount=1000,
        )
        self.opportunity_lost = Opportunity.objects.create(
            company=self.company,
            customer=self.customer,
            source_lead=self.lead_qualified,
            title="Lost Opp",
            stage="LOST",
            amount=500,
        )
        self.opportunity_open = Opportunity.objects.create(
            company=self.company,
            customer=self.customer,
            source_lead=self.lead_new,
            title="Open Opp",
            stage="NEGOTIATION",
            amount=2500,
        )

        now = timezone.now()
        self.overdue_activity = CommercialActivity.objects.create(
            company=self.company,
            type=CommercialActivity.TYPE_MEETING,
            kind=CommercialActivity.KIND_MEETING,
            origin=CommercialActivity.ORIGIN_CUSTOMER,
            customer=self.customer,
            title="Overdue Meeting",
            status=CommercialActivity.STATUS_OPEN,
            start_at=now - timedelta(hours=2),
            end_at=now - timedelta(hours=1),
            remind_at=now - timedelta(hours=3),
        )
        self.open_activity = CommercialActivity.objects.create(
            company=self.company,
            type=CommercialActivity.TYPE_TASK,
            kind=CommercialActivity.KIND_TASK,
            origin=CommercialActivity.ORIGIN_LEAD,
            lead=self.lead_new,
            title="Open Task",
            status=CommercialActivity.STATUS_OPEN,
            start_at=now + timedelta(hours=4),
        )

    def test_sales_flow_summary_returns_expected_metrics(self):
        self.client.force_login(self.member)
        response = self.client.get(
            "/api/sales-flow/summary/",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["leads_new"], 1)
        self.assertEqual(payload["leads_qualified"], 1)
        self.assertEqual(payload["leads_converted"], 1)
        self.assertEqual(payload["opportunities_won"], 1)
        self.assertEqual(payload["winrate"], 0.5)
        self.assertEqual(payload["pipeline_open"], 2500.0)
        self.assertEqual(payload["activities_open"], 2)
        self.assertEqual(payload["activities_overdue"], 1)

    def test_member_cannot_create_activity_or_agenda(self):
        self.client.force_login(self.member)

        activity_response = self.client.post(
            "/api/activities/",
            data={
                "kind": CommercialActivity.KIND_TASK,
                "title": "Member Task",
                "lead": self.lead_new.id,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(activity_response.status_code, 403)

        agenda_response = self.client.post(
            "/api/agenda/",
            data={
                "title": "Member Meeting",
                "subject": "Subject",
                "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "end_at": (timezone.now() + timedelta(days=1, hours=1)).isoformat(),
                "customer": self.customer.id,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(agenda_response.status_code, 403)

    def test_manager_can_create_activity_using_existing_endpoint(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/api/activities/",
            data={
                "kind": CommercialActivity.KIND_TASK,
                "title": "Manager Task",
                "lead": self.lead_new.id,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["title"], "Manager Task")

    @patch("operational.views.EmailService.send_email", return_value=1)
    def test_agenda_flow_create_list_reminders_ack_confirm_cancel(self, _send_email):
        self.client.force_login(self.manager)
        start_at = timezone.now() + timedelta(days=1)
        end_at = start_at + timedelta(hours=1)

        create_response = self.client.post(
            "/api/agenda/",
            data={
                "title": "Reuniao Comercial",
                "subject": "Alinhamento de proposta",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "attendee_name": "Contato Cliente",
                "attendee_email": "contato@cliente.test",
                "send_invite": True,
                "customer": self.customer.id,
            },
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["status"], CommercialActivity.STATUS_OPEN)
        self.assertEqual(created["origin"], CommercialActivity.ORIGIN_CUSTOMER)
        self.assertEqual(created["reminder_state"], CommercialActivity.REMINDER_PENDING)
        self.assertIsNotNone(created["invite_sent_at"])

        agenda_id = created["id"]
        agenda = CommercialActivity.all_objects.get(pk=agenda_id)
        self.assertEqual(agenda.type, CommercialActivity.TYPE_MEETING)
        self.assertEqual(agenda.kind, CommercialActivity.KIND_MEETING)

        list_response = self.client.get(
            "/api/agenda/",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertGreaterEqual(len(list_payload["results"]), 1)

        agenda.remind_at = timezone.now() - timedelta(minutes=1)
        agenda.status = CommercialActivity.STATUS_OPEN
        agenda.reminder_state = CommercialActivity.REMINDER_PENDING
        agenda.save(update_fields=("remind_at", "status", "reminder_state", "updated_at"))

        reminders_response = self.client.get(
            "/api/agenda/reminders/",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(reminders_response.status_code, 200)
        reminders_payload = reminders_response.json()["results"]
        self.assertTrue(any(item["id"] == agenda_id for item in reminders_payload))

        ack_response = self.client.post(
            f"/api/agenda/{agenda_id}/ack-reminder/",
            data={},
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(ack_response.status_code, 200)
        self.assertEqual(
            ack_response.json()["reminder_state"],
            CommercialActivity.REMINDER_ACKED,
        )

        confirm_response = self.client.post(
            f"/api/agenda/{agenda_id}/confirm/",
            data={"send_email": True},
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(confirm_response.status_code, 200)
        confirmed = confirm_response.json()
        self.assertEqual(confirmed["status"], CommercialActivity.STATUS_CONFIRMED)
        self.assertIsNotNone(confirmed["confirmed_at"])

        duplicate_confirm_response = self.client.post(
            f"/api/agenda/{agenda_id}/confirm/",
            data={"send_email": True},
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(duplicate_confirm_response.status_code, 409)

        cancel_response = self.client.post(
            f"/api/agenda/{agenda_id}/cancel/",
            data={},
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(cancel_response.status_code, 200)
        canceled = cancel_response.json()
        self.assertEqual(canceled["status"], CommercialActivity.STATUS_CANCELED)
        self.assertIsNotNone(canceled["canceled_at"])

        duplicate_cancel_response = self.client.post(
            f"/api/agenda/{agenda_id}/cancel/",
            data={},
            content_type="application/json",
            HTTP_X_TENANT_ID="sales-company",
        )
        self.assertEqual(duplicate_cancel_response.status_code, 409)
        self.assertEqual(_send_email.call_count, 4)
