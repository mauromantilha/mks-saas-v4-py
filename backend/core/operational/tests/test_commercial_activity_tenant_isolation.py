from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from customers.models import Company
from operational.models import CommercialActivity, Customer, Lead, Opportunity
from tenancy.context import reset_current_company, set_current_company


class CommercialActivityTenantIsolationTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Company A",
            tenant_code="activity-a",
            subdomain="activity-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Company B",
            tenant_code="activity-b",
            subdomain="activity-b",
            is_active=True,
        )

        token = set_current_company(self.company_a)
        try:
            self.customer_a = Customer.objects.create(
                company=self.company_a,
                name="Customer A",
                email="customer-a@test.com",
            )
            self.lead_a = Lead.objects.create(
                company=self.company_a,
                source="Website",
                email="lead-a@test.com",
                company_name="Lead A LTDA",
            )
            self.opportunity_a = Opportunity.objects.create(
                company=self.company_a,
                customer=self.customer_a,
                source_lead=self.lead_a,
                title="Opp A",
                stage="NEW",
                amount=1000,
            )
            self.activity_a = CommercialActivity.objects.create(
                company=self.company_a,
                type=CommercialActivity.TYPE_TASK,
                origin=CommercialActivity.ORIGIN_LEAD,
                title="Activity A",
                lead=self.lead_a,
                start_at=timezone.now(),
            )
        finally:
            reset_current_company(token)

        token = set_current_company(self.company_b)
        try:
            self.customer_b = Customer.objects.create(
                company=self.company_b,
                name="Customer B",
                email="customer-b@test.com",
            )
            self.lead_b = Lead.objects.create(
                company=self.company_b,
                source="Import",
                email="lead-b@test.com",
                company_name="Lead B SA",
            )
            self.opportunity_b = Opportunity.objects.create(
                company=self.company_b,
                customer=self.customer_b,
                source_lead=self.lead_b,
                title="Opp B",
                stage="NEW",
                amount=2000,
            )
            self.activity_b = CommercialActivity.objects.create(
                company=self.company_b,
                type=CommercialActivity.TYPE_FOLLOW_UP,
                origin=CommercialActivity.ORIGIN_OPPORTUNITY,
                title="Activity B",
                opportunity=self.opportunity_b,
                start_at=timezone.now(),
            )
        finally:
            reset_current_company(token)

    def test_default_manager_scopes_by_current_tenant(self):
        token = set_current_company(self.company_a)
        try:
            ids = list(CommercialActivity.objects.values_list("id", flat=True))
            self.assertEqual(ids, [self.activity_a.id])
        finally:
            reset_current_company(token)

        token = set_current_company(self.company_b)
        try:
            ids = list(CommercialActivity.objects.values_list("id", flat=True))
            self.assertEqual(ids, [self.activity_b.id])
        finally:
            reset_current_company(token)

    def test_cross_tenant_relation_is_blocked(self):
        token = set_current_company(self.company_a)
        try:
            with self.assertRaises(ValidationError):
                CommercialActivity.objects.create(
                    company=self.company_a,
                    type=CommercialActivity.TYPE_TASK,
                    origin=CommercialActivity.ORIGIN_LEAD,
                    title="Invalid cross tenant",
                    lead=self.lead_b,
                    start_at=timezone.now(),
                )
        finally:
            reset_current_company(token)
