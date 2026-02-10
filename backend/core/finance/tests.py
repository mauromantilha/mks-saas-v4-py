from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase

from customers.models import Company
from finance.models import IntegrationInbox, ReceivableInstallment, ReceivableInvoice
from insurance_core.models import Insurer, InsuranceProduct, Policy, PolicyBillingConfig
from ledger.models import LedgerEntry
from operational.models import Customer
from tenancy.context import reset_current_company, set_current_company


class FinanceIntegrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Fin Corp", tenant_code="fin", subdomain="fin")
        self._supports_schema_switch = hasattr(connection, "set_tenant")
        if self._supports_schema_switch:
            connection.set_tenant(self.company)
        self._tenant_token = set_current_company(self.company)
        self.customer = Customer.all_objects.create(
            company=self.company,
            name="John Doe",
            email="john@example.com",
        )

        self.insurer = Insurer.objects.create(company=self.company, name="Seguradora A")
        self.product = InsuranceProduct.objects.create(
            company=self.company,
            insurer=self.insurer,
            code="AUTO-1",
            name="Auto Premium",
            line_of_business=InsuranceProduct.LineOfBusiness.AUTO,
        )

        self.policy = Policy.objects.create(
            company=self.company,
            insurer=self.insurer,
            product=self.product,
            insured_party_id=self.customer.id,
            insured_party_label=self.customer.name,
            policy_number="12345",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            status=Policy.Status.ISSUED,
        )

    def tearDown(self):
        reset_current_company(self._tenant_token)
        if hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()
        super().tearDown()

    def test_create_receivables_consumer_logic(self):
        from finance.services import create_receivables_from_policy_event

        PolicyBillingConfig.objects.create(
            company=self.company,
            policy=self.policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=3,
            premium_total=Decimal("100.00"),
            commission_rate_percent=Decimal("10.00"),
        )

        event = {"id": "evt_test_1", "data": {"policy_id": self.policy.id}}
        create_receivables_from_policy_event(event, self.company)

        invoice = ReceivableInvoice.objects.get(company=self.company, policy=self.policy)
        self.assertEqual(invoice.total_amount, Decimal("100.00"))
        self.assertEqual(invoice.payer_id, self.customer.id)

        installments = invoice.installments.all().order_by("number")
        self.assertEqual(installments.count(), 3)
        self.assertEqual(installments[0].amount, Decimal("33.33"))
        self.assertEqual(installments[1].amount, Decimal("33.33"))
        self.assertEqual(installments[2].amount, Decimal("33.34"))

        self.assertEqual(installments[0].due_date, date(2026, 1, 10))
        self.assertEqual(installments[1].due_date, date(2026, 2, 10))
        self.assertEqual(installments[2].due_date, date(2026, 3, 10))

        ledger_entry = LedgerEntry.objects.filter(
            company=self.company,
            event_type="FINANCE_RECEIVABLES_GENERATED",
            resource_pk=str(invoice.pk),
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
            commission_rate_percent=Decimal("10.00"),
        )

        event = {"id": "evt_idempotent", "data": {"policy_id": self.policy.id}}
        create_receivables_from_policy_event(event, self.company)
        create_receivables_from_policy_event(event, self.company)

        self.assertEqual(ReceivableInvoice.objects.count(), 1)
        self.assertEqual(ReceivableInstallment.objects.count(), 1)
        self.assertEqual(IntegrationInbox.objects.count(), 1)

    def test_settle_installment_updates_invoice_status(self):
        from finance.services import settle_receivable_installment

        invoice = ReceivableInvoice.objects.create(
            company=self.company,
            payer=self.customer,
            policy=self.policy,
            total_amount=Decimal("120.00"),
            status=ReceivableInvoice.STATUS_OPEN,
            issue_date=date(2026, 1, 1),
            description="Teste baixa",
        )
        installment1 = ReceivableInstallment.objects.create(
            company=self.company,
            invoice=invoice,
            number=1,
            amount=Decimal("60.00"),
            due_date=date(2026, 1, 10),
            status=ReceivableInstallment.STATUS_OPEN,
        )
        installment2 = ReceivableInstallment.objects.create(
            company=self.company,
            invoice=invoice,
            number=2,
            amount=Decimal("60.00"),
            due_date=date(2026, 2, 10),
            status=ReceivableInstallment.STATUS_OPEN,
        )

        settle_receivable_installment(company=self.company, installment=installment1, actor=None)
        invoice.refresh_from_db()
        installment1.refresh_from_db()
        self.assertEqual(installment1.status, ReceivableInstallment.STATUS_PAID)
        self.assertEqual(invoice.status, ReceivableInvoice.STATUS_OPEN)

        settle_receivable_installment(company=self.company, installment=installment2, actor=None)
        invoice.refresh_from_db()
        installment2.refresh_from_db()
        self.assertEqual(installment2.status, ReceivableInstallment.STATUS_PAID)
        self.assertEqual(invoice.status, ReceivableInvoice.STATUS_PAID)

    def test_settle_installment_blocks_cross_tenant(self):
        from django.core.exceptions import ValidationError
        from finance.services import settle_receivable_installment

        if self._supports_schema_switch and hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()
        other_company = Company.objects.create(
            name="Other Corp",
            tenant_code="other",
            subdomain="other",
        )
        if self._supports_schema_switch:
            connection.set_tenant(self.company)
        invoice = ReceivableInvoice.objects.create(
            company=self.company,
            payer=self.customer,
            policy=self.policy,
            total_amount=Decimal("50.00"),
            status=ReceivableInvoice.STATUS_OPEN,
            issue_date=date(2026, 1, 1),
            description="Isolamento",
        )
        installment = ReceivableInstallment.objects.create(
            company=self.company,
            invoice=invoice,
            number=1,
            amount=Decimal("50.00"),
            due_date=date(2026, 1, 10),
            status=ReceivableInstallment.STATUS_OPEN,
        )

        with self.assertRaises(ValidationError):
            settle_receivable_installment(
                company=other_company,
                installment=installment,
                actor=None,
            )
