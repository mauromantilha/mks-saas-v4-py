from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from customers.models import Company
from operational.models import Customer
from insurance_core.models import (
    Insurer, InsuranceBranch, InsuranceProduct, Policy, PolicyBillingConfig
)
from finance.models import ReceivableInvoice, ReceivableInstallment, IntegrationInbox
from ledger.models import LedgerEntry

class FinanceIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Fin Corp", tenant_code="fin", subdomain="fin")
        self.user = User.objects.create_user(username="finuser", email="fin@test.com")
        self.customer = Customer.all_objects.create(company=self.company, name="John Doe", email="john@example.com")
        
        self.insurer = Insurer.objects.create(company=self.company, name="Seguradora A")
        self.branch = InsuranceBranch.objects.create(
            company=self.company, name="Auto", branch_type=InsuranceBranch.TYPE_NORMAL
        )
        self.product = InsuranceProduct.objects.create(
            company=self.company, insurer=self.insurer, branch=self.branch, name="Auto Premium"
        )
        
        self.policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="12345",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            status=Policy.STATUS_QUOTED
        )

    def test_issue_policy_service_publishes_event(self):
        from insurance_core.services import issue_policy
        from ledger.models import LedgerEntry

        issue_policy(self.policy, self.user)
        
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.status, Policy.STATUS_ISSUED)
        self.assertIsNotNone(self.policy.issue_date)

        # Check if event was published to ledger
        event = LedgerEntry.objects.filter(
            company=self.company, 
            event_type="POLICY_ISSUED",
            resource_pk=str(self.policy.pk)
        ).first()
        self.assertIsNotNone(event)

    def test_create_receivables_consumer_logic(self):
        from finance.services import create_receivables_from_policy_event

        # Setup billing config
        PolicyBillingConfig.objects.create(
            company=self.company,
            policy=self.policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=3,
            premium_total=Decimal("100.00"),
            commission_rate_percent=Decimal("10.00")
        )

        event = {"id": "evt_test_1", "data": {"policy_id": self.policy.id}}
        create_receivables_from_policy_event(event, self.company)

        # Check Invoice
        invoice = ReceivableInvoice.objects.get(company=self.company, policy=self.policy)
        self.assertEqual(invoice.total_amount, Decimal("100.00"))
        self.assertEqual(invoice.payer, self.customer)

        # Check Installments (100 / 3 = 33.33, diff 0.01 on LAST)
        installments = invoice.installments.all().order_by("number")
        self.assertEqual(installments.count(), 3)
        
        self.assertEqual(installments[0].amount, Decimal("33.33"))
        self.assertEqual(installments[0].due_date, date(2026, 1, 10))
        
        self.assertEqual(installments[1].amount, Decimal("33.33"))
        self.assertEqual(installments[1].due_date, date(2026, 2, 10))
        
        self.assertEqual(installments[2].amount, Decimal("33.34"))
        self.assertEqual(installments[2].due_date, date(2026, 3, 10))

        # Check Audit Event (Ledger)
        ledger_entry = LedgerEntry.objects.filter(
            company=self.company,
            event_type="FINANCE_RECEIVABLES_GENERATED",
            resource_pk=str(invoice.pk)
        ).first()
        self.assertIsNotNone(ledger_entry)

    def test_create_receivables_idempotency(self):
        from finance.services import create_receivables_from_policy_event

        PolicyBillingConfig.objects.create(
            company=self.company,
            policy=self.policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=1,
            premium_total=Decimal("100.00"),
            commission_rate_percent=Decimal("10.00")
        )

        event = {"id": "evt_idempotent", "data": {"policy_id": self.policy.id}}
        
        create_receivables_from_policy_event(event, self.company)
        create_receivables_from_policy_event(event, self.company)

        self.assertEqual(ReceivableInvoice.objects.count(), 1)
        self.assertEqual(IntegrationInbox.objects.count(), 1)