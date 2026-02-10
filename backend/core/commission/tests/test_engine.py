from decimal import Decimal
from datetime import date
from django.test import TestCase
from customers.models import Company
from operational.models import Customer, OperationalIntegrationInbox
from commission.models import CommissionAccrual
from insurance_core.models import Insurer, InsuranceBranch, InsuranceProduct, Policy, PolicyBillingConfig
from finance.models import ReceivableInvoice, ReceivableInstallment
from commission.services import process_installment_paid_event

class CommissionEngineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Comm Corp", tenant_code="comm", subdomain="comm")
        self.customer = Customer.all_objects.create(company=self.company, name="John Doe", email="john@example.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Seguradora A")
        
        self.branch_normal = InsuranceBranch.objects.create(
            company=self.company, name="Auto", branch_type=InsuranceBranch.TYPE_NORMAL, code="01"
        )
        self.branch_health = InsuranceBranch.objects.create(
            company=self.company, name="Saúde", branch_type=InsuranceBranch.TYPE_HEALTH, code="02"
        )
        
        self.product_normal = InsuranceProduct.objects.create(
            company=self.company, insurer=self.insurer, branch=self.branch_normal, name="Auto Product"
        )
        self.product_health = InsuranceProduct.objects.create(
            company=self.company, insurer=self.insurer, branch=self.branch_health, name="Health Product"
        )

    def _create_policy_and_installment(self, product, is_renewal, premium_total, installment_amount, installment_number, original_premium=None, commission_rate=None):
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=product,
            branch=product.branch,
            policy_number="123",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            is_renewal=is_renewal
        )
        PolicyBillingConfig.objects.create(
            company=self.company,
            policy=policy,
            first_installment_due_date=date(2026, 1, 1),
            installments_count=12,
            premium_total=premium_total,
            original_premium_total=original_premium or premium_total,
            commission_rate_percent=commission_rate or Decimal("0")
        )
        invoice = ReceivableInvoice.objects.create(
            company=self.company, payer=self.customer, policy=policy, total_amount=premium_total, issue_date=date(2026, 1, 1)
        )
        installment = ReceivableInstallment.objects.create(
            company=self.company, invoice=invoice, number=installment_number, amount=installment_amount, due_date=date(2026, 1, 1)
        )
        return installment

    def test_normal_branch_commission(self):
        # Normal: 1000 premium, 15% commission. Installment 100.
        installment = self._create_policy_and_installment(
            self.product_normal, False, Decimal("1200"), Decimal("100.00"), 1, commission_rate=Decimal("15.00")
        )
        
        event = {"id": "evt_1", "data": {"installment_id": installment.id}}
        process_installment_paid_event(event, self.company)
        
        accrual = CommissionAccrual.objects.get(company=self.company)
        self.assertEqual(accrual.amount, Decimal("15.00")) # 100 * 15%

    def test_health_new_business_first_3_installments(self):
        # Health New: Installment 1. Should be 100%.
        installment = self._create_policy_and_installment(
            self.product_health, False, Decimal("1200"), Decimal("100.00"), 1
        )
        
        event = {"id": "evt_2", "data": {"installment_id": installment.id}}
        process_installment_paid_event(event, self.company)
        
        accrual = CommissionAccrual.objects.get(company=self.company)
        self.assertEqual(accrual.amount, Decimal("100.00"))

    def test_health_new_business_4th_installment(self):
        # Health New: Installment 4. Should be 2%.
        installment = self._create_policy_and_installment(
            self.product_health, False, Decimal("1200"), Decimal("100.00"), 4
        )
        
        event = {"id": "evt_3", "data": {"installment_id": installment.id}}
        process_installment_paid_event(event, self.company)
        
        accrual = CommissionAccrual.objects.get(company=self.company)
        self.assertEqual(accrual.amount, Decimal("2.00")) # 100 * 2%

    def test_health_renewal(self):
        # Health Renewal: Installment 1. Should be 2%.
        installment = self._create_policy_and_installment(
            self.product_health, True, Decimal("1200"), Decimal("100.00"), 1
        )
        
        event = {"id": "evt_4", "data": {"installment_id": installment.id}}
        process_installment_paid_event(event, self.company)
        
        accrual = CommissionAccrual.objects.get(company=self.company)
        self.assertEqual(accrual.amount, Decimal("2.00"))

    def test_health_endorsement_delta_logic(self):
        # Health New: Installment 2 (within first 3).
        # Original Premium: 1200 (100/mo).
        # Endorsed Premium: 1440 (120/mo). Delta is 20.
        # Commission should be: 100 (base @ 100%) + 20 (delta @ 2%) = 100.40
        
        installment = self._create_policy_and_installment(
            self.product_health, 
            False, 
            premium_total=Decimal("1440.00"), # Current total
            installment_amount=Decimal("120.00"), # Current installment
            installment_number=2,
            original_premium=Decimal("1200.00") # Original total
        )
        
        event = {"id": "evt_5", "data": {"installment_id": installment.id}}
        process_installment_paid_event(event, self.company)
        
        accrual = CommissionAccrual.objects.get(company=self.company)
        # Base: 100.00 * 1.00 = 100.00
        # Delta: 20.00 * 0.02 = 0.40
        # Total: 100.40
        self.assertEqual(accrual.amount, Decimal("100.40"))

    def test_idempotency(self):
        installment = self._create_policy_and_installment(
            self.product_normal, False, Decimal("1200"), Decimal("100.00"), 1, commission_rate=Decimal("10.00")
        )
        
        event = {"id": "evt_idem", "data": {"installment_id": installment.id}}
        
        # First call
        process_installment_paid_event(event, self.company)
        self.assertEqual(CommissionAccrual.objects.count(), 1)
        self.assertEqual(OperationalIntegrationInbox.objects.count(), 1)
        
        # Second call
        process_installment_paid_event(event, self.company)
        self.assertEqual(CommissionAccrual.objects.count(), 1)