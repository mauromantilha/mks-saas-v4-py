from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from uuid import uuid4
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from customers.models import Company, CompanyMembership
from operational.models import Customer
from insurance_core.models import (
    Insurer,
    InsuranceBranch,
    InsuranceProduct,
    Policy,
    PolicyBillingConfig,
    Endorsement,
    Claim,
    PolicyDocument,
    DomainEventOutbox
)
from finance.models import ReceivableInvoice, ReceivableInstallment
from operational.models import OperationalIntegrationInbox
from commission.models import CommissionAccrual
from finance.services import create_receivables_from_policy_event, process_endorsement_financial_impact
from commission.services import process_installment_paid_event
from insurance_core.services import issue_policy, create_endorsement

class PolicyModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Corp", tenant_code="test", subdomain="test")
        self.customer = Customer.all_objects.create(company=self.company, name="John Doe", email="john@example.com")
        
        self.insurer = Insurer.objects.create(company=self.company, name="Seguradora A")
        self.branch = InsuranceBranch.objects.create(
            company=self.company, 
            name="Automóvel", 
            code="0531", 
            branch_type=InsuranceBranch.TYPE_NORMAL
        )
        self.product = InsuranceProduct.objects.create(
            company=self.company, 
            insurer=self.insurer, 
            branch=self.branch, 
            name="Auto Premium"
        )

    def test_policy_dates_validation(self):
        policy = Policy(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="12345",
            start_date=date(2026, 1, 1),
            end_date=date(2025, 1, 1), # Invalid: before start
            status=Policy.STATUS_ACTIVE
        )
        with self.assertRaises(ValidationError) as cm:
            policy.full_clean()
        self.assertIn("end_date", cm.exception.message_dict)

    def test_billing_config_installments_validation(self):
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="12345",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
        )

        # Test > 12
        config_invalid = PolicyBillingConfig(
            company=self.company,
            policy=policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=13,
            premium_total="1000.00",
            commission_rate_percent="10.00"
        )
        with self.assertRaises(ValidationError) as cm:
            config_invalid.full_clean()
        self.assertIn("installments_count", cm.exception.message_dict)

        # Test < 1
        config_invalid.installments_count = 0
        with self.assertRaises(ValidationError) as cm:
            config_invalid.full_clean()
        self.assertIn("installments_count", cm.exception.message_dict)

        # Test Valid
        config_valid = PolicyBillingConfig(
            company=self.company,
            policy=policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=12,
            premium_total="1000.00",
            commission_rate_percent="10.00"
        )
        config_valid.full_clean() # Should not raise

    def test_health_plan_flag(self):
        health_branch = InsuranceBranch.objects.create(
            company=self.company, name="Saúde", branch_type=InsuranceBranch.TYPE_HEALTH
        )
        policy = Policy(branch=health_branch)
        self.assertTrue(policy.is_health_plan)


class EndorsementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Endorse Corp", tenant_code="endorse", subdomain="endorse")
        self.customer = Customer.all_objects.create(company=self.company, name="Jane Doe", email="jane@example.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Seguradora B")
        self.branch = InsuranceBranch.objects.create(company=self.company, name="Auto", branch_type=InsuranceBranch.TYPE_NORMAL)
        self.product = InsuranceProduct.objects.create(company=self.company, insurer=self.insurer, branch=self.branch, name="Auto Gold")
        
        self.policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="POL-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Policy.STATUS_ISSUED
        )
        self.billing = PolicyBillingConfig.objects.create(
            company=self.company,
            policy=self.policy,
            first_installment_due_date=date(2026, 1, 10),
            installments_count=12,
            premium_total=Decimal("1200.00"),
            commission_rate_percent=Decimal("10.00")
        )
        
        # Simulate Finance Receivables creation (usually done by event consumer)
        from finance.models import ReceivableInvoice, ReceivableInstallment
        self.invoice = ReceivableInvoice.objects.create(
            company=self.company, payer=self.customer, policy=self.policy, total_amount=Decimal("1200.00"), issue_date=date(2026, 1, 1)
        )
        for i in range(1, 13):
            ReceivableInstallment.objects.create(
                company=self.company, invoice=self.invoice, number=i, amount=Decimal("100.00"), 
                due_date=date(2026, 1, 10) + timedelta(days=30*(i-1)),
                status=ReceivableInstallment.STATUS_OPEN
            )

    def test_premium_increase_endorsement(self):
        from insurance_core.services import create_endorsement
        from finance.services import process_endorsement_financial_impact

        # Increase by 100.00 effective from installment 6 (approx June)
        effective_date = date(2026, 6, 1)
        endorsement = create_endorsement(
            self.policy, Endorsement.TYPE_INCREASE, effective_date, premium_delta=Decimal("100.00")
        )

        # Simulate event processing
        event = {
            "id": "evt_inc_1",
            "data": {
                "policy_id": self.policy.id,
                "endorsement_type": Endorsement.TYPE_INCREASE,
                "premium_delta": "100.00",
                "effective_date": str(effective_date)
            }
        }
        process_endorsement_financial_impact(event, self.company)

        # Check installments. Installments 1-5 should be 100. Installments 6-12 (7 installments) should share the delta.
        # 100 / 7 = 14.28. First gets 14.32.
        from finance.models import ReceivableInstallment
        inst_5 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=5)
        inst_6 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=6)
        inst_7 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=7)

        self.assertEqual(inst_5.amount, Decimal("100.00")) # Unchanged
        self.assertGreater(inst_6.amount, Decimal("100.00")) # Increased
        self.assertEqual(inst_6.amount + inst_7.amount * 6, Decimal("100.00") * 7 + Decimal("100.00")) # Total check

    def test_cancellation_endorsement(self):
        from insurance_core.services import create_endorsement
        from finance.services import process_endorsement_financial_impact
        from finance.models import ReceivableInstallment

        effective_date = date(2026, 4, 1)
        create_endorsement(self.policy, Endorsement.TYPE_CANCEL, effective_date)
        
        event = {
            "id": "evt_cancel_1",
            "data": {"policy_id": self.policy.id, "endorsement_type": Endorsement.TYPE_CANCEL, "effective_date": str(effective_date)}
        }
        process_endorsement_financial_impact(event, self.company)

        self.policy.refresh_from_db()
        self.assertEqual(self.policy.status, Policy.STATUS_CANCELLED)
        
        # Installments due after April 1st should be cancelled
        cancelled_count = ReceivableInstallment.objects.filter(company=self.company, invoice=self.invoice, status=ReceivableInstallment.STATUS_CANCELLED).count()
        self.assertTrue(cancelled_count > 0)

    def test_premium_decrease_endorsement(self):
        from insurance_core.services import create_endorsement
        from finance.services import process_endorsement_financial_impact
        from finance.models import ReceivableInstallment

        # Decrease by 50.00 effective from installment 4 (April)
        effective_date = date(2026, 4, 1)
        create_endorsement(
            self.policy, Endorsement.TYPE_DECREASE, effective_date, premium_delta=Decimal("-50.00")
        )

        event = {
            "id": "evt_dec_1",
            "data": {
                "policy_id": self.policy.id,
                "endorsement_type": Endorsement.TYPE_DECREASE,
                "premium_delta": "-50.00",
                "effective_date": str(effective_date)
            }
        }
        process_endorsement_financial_impact(event, self.company)

        # Installments 4-12 (9 installments). Delta -50.
        # -50 / 9 = -5.555... -> -5.56 (quantize)
        # -5.56 * 9 = -50.04. Remainder = -50 - (-50.04) = 0.04.
        # Inst 4: 100 + (-5.56 + 0.04) = 94.48
        # Inst 5: 100 + (-5.56) = 94.44
        inst_4 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=4)
        inst_5 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=5)
        
        self.assertEqual(inst_4.amount, Decimal("94.48"))
        self.assertEqual(inst_5.amount, Decimal("94.44"))
        
        # Verify total
        total_new = sum(i.amount for i in ReceivableInstallment.objects.filter(company=self.company, invoice=self.invoice, number__gte=4))
        # Original total for 9 inst: 900.
        # New total should be 850.
        self.assertEqual(total_new, Decimal("850.00"))

    def test_no_movement_endorsement(self):
        from insurance_core.services import create_endorsement
        from finance.services import process_endorsement_financial_impact
        from finance.models import ReceivableInstallment

        effective_date = date(2026, 5, 1)
        create_endorsement(
            self.policy, Endorsement.TYPE_NO_MOVE, effective_date, description="Mudança de endereço"
        )

        event = {
            "id": "evt_nomove_1",
            "data": {
                "policy_id": self.policy.id,
                "endorsement_type": Endorsement.TYPE_NO_MOVE,
                "premium_delta": "0.00",
                "effective_date": str(effective_date)
            }
        }
        process_endorsement_financial_impact(event, self.company)

        # Installments should be unchanged
        inst_5 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=5)
        self.assertEqual(inst_5.amount, Decimal("100.00"))

    def test_health_add_beneficiary_endorsement(self):
        from insurance_core.services import create_endorsement
        from finance.services import process_endorsement_financial_impact
        from finance.models import ReceivableInstallment
        from commission.engine import CommissionEngine

        # Setup Health Policy
        health_branch = InsuranceBranch.objects.create(
            company=self.company, name="Saúde", branch_type=InsuranceBranch.TYPE_HEALTH, code="99"
        )
        self.policy.branch = health_branch
        self.policy.save()
        self.product.branch = health_branch
        self.product.save()
        
        # Set original premium to track base for commission
        self.billing.original_premium_total = Decimal("1200.00")
        self.billing.save()

        # Add Beneficiary: Increase by 120.00 effective from installment 2 (Feb)
        # Remaining installments: 2..12 (11 installments)
        # Delta per installment: 120 / 11 = 10.909... -> approx 10.91
        effective_date = date(2026, 2, 1)
        create_endorsement(
            self.policy, Endorsement.TYPE_HEALTH_ADD_BENEFICIARY, effective_date, premium_delta=Decimal("120.00")
        )

        event = {
            "id": "evt_health_add_1",
            "data": {
                "policy_id": self.policy.id,
                "endorsement_type": Endorsement.TYPE_HEALTH_ADD_BENEFICIARY,
                "premium_delta": "120.00",
                "effective_date": str(effective_date)
            }
        }
        process_endorsement_financial_impact(event, self.company)

        # Verify Installment 2 (Impacted)
        inst_2 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=2)
        # Original 100 + Delta part. 
        # 120 total delta / 11 installments = 10.90. First of batch gets remainder.
        # 10.90 * 11 = 119.90. Remainder 0.10.
        # Inst 2 gets 10.90 + 0.10 = 11.00. Total 111.00.
        self.assertEqual(inst_2.amount, Decimal("111.00"))

        # Verify Commission Logic for Installment 2 (Early stage - < 4)
        # Rule: Base (100) at 100%, Delta (11) at 2%.
        # Expected: 100 + (11 * 0.02) = 100.22
        engine = CommissionEngine()
        comm_2 = engine.calculate(self.policy, 2, inst_2.amount)
        self.assertEqual(comm_2, Decimal("100.22"))

        # Verify Installment 6 (Later stage - > 3)
        inst_6 = ReceivableInstallment.objects.get(company=self.company, invoice=self.invoice, number=6)
        # Should have 10.90 delta. Total 110.90.
        self.assertEqual(inst_6.amount, Decimal("110.90"))

        # Verify Commission Logic for Installment 6
        # Rule: Base (100) at 2%, Delta (10.90) at 2%.
        # Effectively 2% on total.
        # Expected: 110.90 * 0.02 = 2.218 -> 2.22
        comm_6 = engine.calculate(self.policy, 6, inst_6.amount)
        self.assertEqual(comm_6, Decimal("2.22"))

        # Verify Billing Config Updated
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.premium_total, Decimal("1320.00")) # 1200 + 120
        self.assertEqual(self.billing.original_premium_total, Decimal("1200.00")) # Unchanged


class PolicyAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="API Corp", tenant_code="api-corp", subdomain="api-corp")
        self.user = User.objects.create_user(username="api_user", email="api@corp.com")
        CompanyMembership.objects.create(company=self.company, user=self.user, role=CompanyMembership.ROLE_OWNER)
        
        self.customer = Customer.all_objects.create(company=self.company, name="John API", email="john@api.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Insurer API")
        self.branch = InsuranceBranch.objects.create(company=self.company, name="Branch API", branch_type=InsuranceBranch.TYPE_NORMAL)
        self.product = InsuranceProduct.objects.create(company=self.company, insurer=self.insurer, branch=self.branch, name="Product API")

    def test_issue_policy_endpoint(self):
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="POL-API-001",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            status=Policy.STATUS_QUOTED
        )
        
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/insurance/policies/{policy.id}/issue/",
            HTTP_X_TENANT_ID=self.company.tenant_code,
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ISSUED")
        policy.refresh_from_db()
        self.assertEqual(policy.status, Policy.STATUS_ISSUED)

    def test_policy_validation_and_update(self):
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="POL-VAL-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Policy.STATUS_ISSUED # Issued
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2026, 1, 1), installments_count=1, premium_total=100, commission_rate_percent=10
        )

        self.client.force_login(self.user)
        # Try to change start_date on ISSUED policy -> Should fail
        response = self.client.patch(
            f"/api/insurance/policies/{policy.id}/",
            data={"start_date": "2026-02-01"},
            HTTP_X_TENANT_ID=self.company.tenant_code,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot edit start_date", str(response.content))

    def test_renew_policy_endpoint(self):
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="POL-ORIG-001",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            status=Policy.STATUS_ISSUED
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2025, 1, 10), installments_count=12, premium_total=1200, commission_rate_percent=10
        )

        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/insurance/policies/{policy.id}/renew/",
            HTTP_X_TENANT_ID=self.company.tenant_code,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["policy_number"], "POL-ORIG-001-REN")
        self.assertTrue(response.json()["is_renewal"])

    def test_endorsement_simulation_endpoint(self):
        from finance.models import ReceivableInvoice, ReceivableInstallment
        
        policy = Policy.objects.create(
            company=self.company,
            customer=self.customer,
            insurer=self.insurer,
            product=self.product,
            branch=self.branch,
            policy_number="POL-SIM-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Policy.STATUS_ISSUED
        )
        invoice = ReceivableInvoice.objects.create(
            company=self.company, payer=self.customer, policy=policy, total_amount=Decimal("1200.00"), issue_date=date(2026, 1, 1)
        )
        ReceivableInstallment.objects.create(
            company=self.company, invoice=invoice, number=1, amount=Decimal("100.00"), due_date=date(2026, 2, 1), status=ReceivableInstallment.STATUS_OPEN
        )

        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/insurance/policies/{policy.id}/endorsements/preview/",
            data={"endorsement_type": "PREMIUM_INCREASE", "premium_delta": "10.00", "effective_date": "2026-01-01"},
            HTTP_X_TENANT_ID=self.company.tenant_code,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["new_amount"], "110.00")


class ClaimTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Claim Corp", tenant_code="claim", subdomain="claim")
        self.customer = Customer.all_objects.create(company=self.company, name="John Claim", email="john@claim.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Insurer C")
        self.branch = InsuranceBranch.objects.create(company=self.company, name="Auto", branch_type=InsuranceBranch.TYPE_NORMAL)
        self.product = InsuranceProduct.objects.create(company=self.company, insurer=self.insurer, branch=self.branch, name="Product C")
        self.policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product, branch=self.branch,
            policy_number="POL-CLM-001", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_ISSUED
        )

    def test_claim_lifecycle(self):
        from insurance_core.services import create_claim, transition_claim_status

        # 1. Open Claim
        claim = create_claim(
            policy=self.policy,
            occurrence_date=date(2026, 6, 1),
            report_date=date(2026, 6, 2),
            description="Acidente leve",
            amount_claimed=Decimal("2000.00")
        )
        self.assertEqual(claim.status, Claim.STATUS_OPEN)
        self.assertTrue(claim.claim_number.startswith("CLM-"))

        # 2. Transition to Review
        transition_claim_status(claim, Claim.STATUS_IN_REVIEW, notes="Analisando documentos")
        self.assertEqual(claim.status, Claim.STATUS_IN_REVIEW)

        # 3. Approve
        transition_claim_status(claim, Claim.STATUS_APPROVED, amount_approved=Decimal("1800.00"))
        self.assertEqual(claim.status, Claim.STATUS_APPROVED)
        self.assertEqual(claim.amount_approved, Decimal("1800.00"))

        # 4. Invalid Transition (Approved -> Open is not allowed)
        with self.assertRaises(ValidationError):
            transition_claim_status(claim, Claim.STATUS_OPEN)

    @patch("insurance_core.services.settings")
    def test_claim_document_upload_url_generation(self, mock_settings):
        from insurance_core.services import create_document_upload_url
        
        # Mock settings and GCS
        mock_settings.CLOUD_STORAGE_BUCKET = "test-bucket"
        mock_settings.DEBUG = False
        
        with patch.dict("sys.modules", {"google.cloud": MagicMock(), "google.cloud.storage": MagicMock()}):
            import google.cloud.storage
            mock_client = google.cloud.storage.Client.return_value
            mock_bucket = mock_client.bucket.return_value
            mock_blob = mock_bucket.blob.return_value
            mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"

            claim = Claim.objects.create(company=self.company, policy=self.policy, claim_number="CLM-DOC-TEST", occurrence_date=date(2026, 1, 1), report_date=date(2026, 1, 1))
            
            doc, url = create_document_upload_url(self.company, claim, "evidence.pdf", "application/pdf", 1024)
            
            self.assertEqual(url, "https://storage.googleapis.com/signed-url")
            self.assertEqual(doc.bucket_name, "test-bucket")
            self.assertEqual(doc.claim, claim)


class FullIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Integ Corp", tenant_code="integ", subdomain="integ")
        self.user = User.objects.create_user(username="integ_user", email="integ@corp.com")
        self.customer = Customer.all_objects.create(company=self.company, name="John Integ", email="john@integ.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Insurer Integ")
        
        self.branch_normal = InsuranceBranch.objects.create(
            company=self.company, name="Auto", branch_type=InsuranceBranch.TYPE_NORMAL
        )
        self.product_normal = InsuranceProduct.objects.create(
            company=self.company, insurer=self.insurer, branch=self.branch_normal, name="Auto Product"
        )

        self.branch_health = InsuranceBranch.objects.create(
            company=self.company, name="Health", branch_type=InsuranceBranch.TYPE_HEALTH
        )
        self.product_health = InsuranceProduct.objects.create(
            company=self.company, insurer=self.insurer, branch=self.branch_health, name="Health Product"
        )

    def _simulate_event(self, handler, data):
        event_id = str(uuid4())
        event = {"id": event_id, "data": data}
        handler(event, self.company)
        return event_id

    def test_scenario_a_normal_lifecycle(self):
        # 1. Emitir apólice com 6 parcelas
        policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product_normal, branch=self.branch_normal,
            policy_number="POL-A", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_QUOTED
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2026, 1, 10), installments_count=6, premium_total=Decimal("600.00"), commission_rate_percent=Decimal("10.00")
        )

        issue_policy(policy, self.user)
        self.assertEqual(policy.status, Policy.STATUS_ISSUED)

        # 2. Gerar receivables (Simular evento)
        self._simulate_event(create_receivables_from_policy_event, {"policy_id": policy.id})
        
        invoice = ReceivableInvoice.objects.get(policy=policy)
        self.assertEqual(invoice.total_amount, Decimal("600.00"))
        self.assertEqual(invoice.installments.count(), 6)

        # 3. Pagar parcela 1 -> gerar comissão percentual
        inst_1 = invoice.installments.get(number=1)
        inst_1.status = ReceivableInstallment.STATUS_PAID # Simulating payment update
        inst_1.save()
        
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_1.id})
        
        accrual = CommissionAccrual.objects.get(object_id=inst_1.id)
        # 100.00 * 10% = 10.00
        self.assertEqual(accrual.amount, Decimal("10.00"))

        # 4. Endosso aumento -> ajustar parcelas futuras
        # Aumento de 50.00 efetivo na parcela 4 (Abril)
        effective_date = date(2026, 4, 1)
        create_endorsement(policy, Endorsement.TYPE_INCREASE, effective_date, premium_delta=Decimal("50.00"))
        
        self._simulate_event(process_endorsement_financial_impact, {
            "policy_id": policy.id, 
            "endorsement_type": Endorsement.TYPE_INCREASE, 
            "premium_delta": "50.00", 
            "effective_date": str(effective_date)
        })

        # Parcelas 4, 5, 6 (3 parcelas) devem absorver o delta de 50.00
        # 50 / 3 = 16.66... -> 16.66 * 3 = 49.98. Remainder 0.02.
        # Inst 4: 100 + 16.66 + 0.02 = 116.68
        # Inst 5, 6: 100 + 16.66 = 116.66
        inst_4 = invoice.installments.get(number=4)
        inst_5 = invoice.installments.get(number=5)
        self.assertEqual(inst_4.amount, Decimal("116.68"))
        self.assertEqual(inst_5.amount, Decimal("116.66"))

        # 5. Cancelamento -> cancelar parcelas futuras
        cancel_date = date(2026, 5, 1) # Antes da parcela 5
        create_endorsement(policy, Endorsement.TYPE_CANCEL, cancel_date)
        
        self._simulate_event(process_endorsement_financial_impact, {
            "policy_id": policy.id,
            "endorsement_type": Endorsement.TYPE_CANCEL,
            "effective_date": str(cancel_date)
        })

        inst_5.refresh_from_db()
        inst_6 = invoice.installments.get(number=6)
        self.assertEqual(inst_5.status, ReceivableInstallment.STATUS_CANCELLED)
        self.assertEqual(inst_6.status, ReceivableInstallment.STATUS_CANCELLED)
        
        # Inst 4 (due April) should remain OPEN (or PAID if we paid it, but here it is OPEN)
        inst_4.refresh_from_db()
        self.assertEqual(inst_4.status, ReceivableInstallment.STATUS_OPEN)

    def test_scenario_b_health_plan_first_term(self):
        # 1. Emitir apólice 12 parcelas
        policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product_health, branch=self.branch_health,
            policy_number="POL-B", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_QUOTED
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2026, 1, 10), installments_count=12, 
            premium_total=Decimal("1200.00"), original_premium_total=Decimal("1200.00"), commission_rate_percent=Decimal("0")
        )
        issue_policy(policy, self.user)
        self._simulate_event(create_receivables_from_policy_event, {"policy_id": policy.id})
        invoice = ReceivableInvoice.objects.get(policy=policy)

        # 2. Pagar parcela 1..4
        # Inst 1 (Jan) -> 100%
        inst_1 = invoice.installments.get(number=1)
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_1.id})
        accrual_1 = CommissionAccrual.objects.get(object_id=inst_1.id)
        self.assertEqual(accrual_1.amount, Decimal("100.00"))

        # Inst 3 (Mar) -> 100%
        inst_3 = invoice.installments.get(number=3)
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_3.id})
        accrual_3 = CommissionAccrual.objects.get(object_id=inst_3.id)
        self.assertEqual(accrual_3.amount, Decimal("100.00"))

        # Inst 4 (Apr) -> 2%
        inst_4 = invoice.installments.get(number=4)
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_4.id})
        accrual_4 = CommissionAccrual.objects.get(object_id=inst_4.id)
        self.assertEqual(accrual_4.amount, Decimal("2.00"))

        # 3. Endosso inclusão beneficiário no mês 5 (Maio)
        # Aumento de 80.00 total nas parcelas restantes (5..12 = 8 parcelas)
        # Delta por parcela = 10.00
        effective_date = date(2026, 5, 1)
        create_endorsement(policy, Endorsement.TYPE_HEALTH_ADD_BENEFICIARY, effective_date, premium_delta=Decimal("80.00"))
        
        self._simulate_event(process_endorsement_financial_impact, {
            "policy_id": policy.id,
            "endorsement_type": Endorsement.TYPE_HEALTH_ADD_BENEFICIARY,
            "premium_delta": "80.00",
            "effective_date": str(effective_date)
        })

        # 4. Pagar parcela 5
        inst_5 = invoice.installments.get(number=5)
        self.assertEqual(inst_5.amount, Decimal("110.00")) # 100 original + 10 delta
        
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_5.id})
        accrual_5 = CommissionAccrual.objects.get(object_id=inst_5.id)
        
        # Regra: Base (100) já passou da 3ª parcela -> 2% = 2.00
        # Delta (10) -> 2% = 0.20
        # Total = 2.20
        self.assertEqual(accrual_5.amount, Decimal("2.20"))

    def test_scenario_c_health_renewal(self):
        # 1. Emitir apólice renovação
        policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product_health, branch=self.branch_health,
            policy_number="POL-C", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), 
            status=Policy.STATUS_QUOTED, is_renewal=True
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2026, 1, 10), installments_count=12, 
            premium_total=Decimal("1200.00"), original_premium_total=Decimal("1200.00"), commission_rate_percent=Decimal("0")
        )
        issue_policy(policy, self.user)
        self._simulate_event(create_receivables_from_policy_event, {"policy_id": policy.id})
        invoice = ReceivableInvoice.objects.get(policy=policy)

        # 2. Pagar parcela 1 -> 2% (sem regra de 100% nas primeiras)
        inst_1 = invoice.installments.get(number=1)
        self._simulate_event(process_installment_paid_event, {"installment_id": inst_1.id})
        
        accrual_1 = CommissionAccrual.objects.get(object_id=inst_1.id)
        self.assertEqual(accrual_1.amount, Decimal("2.00"))

    def test_idempotency_and_isolation(self):
        # Idempotency check on receivables generation
        policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product_normal, branch=self.branch_normal,
            policy_number="POL-IDEM", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_ISSUED
        )
        PolicyBillingConfig.objects.create(
            company=self.company, policy=policy,
            first_installment_due_date=date(2026, 1, 10), installments_count=1, premium_total=Decimal("100.00"), commission_rate_percent=Decimal("10.00")
        )
        
        self._simulate_event(create_receivables_from_policy_event, {"policy_id": policy.id})
        self._simulate_event(create_receivables_from_policy_event, {"policy_id": policy.id}) # Duplicate
        
        self.assertEqual(ReceivableInvoice.objects.filter(policy=policy).count(), 1)

    def test_outbox_events_are_created(self):
        # 1. Issue Policy -> POLICY_ISSUED
        policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product_normal, branch=self.branch_normal,
            policy_number="POL-OUTBOX", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_QUOTED
        )
        issue_policy(policy, self.user)
        
        event = DomainEventOutbox.objects.filter(company=self.company, event_type="POLICY_ISSUED").last()
        self.assertIsNotNone(event)
        self.assertEqual(event.payload["policy_id"], policy.id)

        # 2. Endorsement -> ENDORSEMENT_APPLIED
        effective_date = date(2026, 6, 1)
        create_endorsement(policy, Endorsement.TYPE_INCREASE, effective_date, premium_delta=Decimal("10.00"))
        
        event = DomainEventOutbox.objects.filter(company=self.company, event_type="ENDORSEMENT_APPLIED").last()
        self.assertIsNotNone(event)
        self.assertEqual(event.payload["policy_id"], policy.id)
        self.assertEqual(event.payload["endorsement_type"], Endorsement.TYPE_INCREASE)

        # 3. Cancellation -> POLICY_CANCELLED
        cancel_date = date(2026, 7, 1)
        create_endorsement(policy, Endorsement.TYPE_CANCEL, cancel_date)
        
        event = DomainEventOutbox.objects.filter(company=self.company, event_type="POLICY_CANCELLED").last()
        self.assertIsNotNone(event)
        self.assertEqual(event.payload["policy_id"], policy.id)
        self.assertEqual(event.payload["endorsement_type"], Endorsement.TYPE_CANCEL)


class DocumentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Doc Corp", tenant_code="doc-corp", subdomain="doc-corp")
        self.user = User.objects.create_user(username="doc_user", email="doc@corp.com")
        CompanyMembership.objects.create(company=self.company, user=self.user, role=CompanyMembership.ROLE_OWNER)
        
        self.customer = Customer.all_objects.create(company=self.company, name="John Doc", email="john@doc.com")
        self.insurer = Insurer.objects.create(company=self.company, name="Insurer D")
        self.branch = InsuranceBranch.objects.create(company=self.company, name="Branch D", branch_type=InsuranceBranch.TYPE_NORMAL)
        self.product = InsuranceProduct.objects.create(company=self.company, insurer=self.insurer, branch=self.branch, name="Product D")
        self.policy = Policy.objects.create(
            company=self.company, customer=self.customer, insurer=self.insurer, product=self.product, branch=self.branch,
            policy_number="POL-DOC-001", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), status=Policy.STATUS_ISSUED
        )

    def test_soft_delete_document(self):
        doc = PolicyDocument.objects.create(
            company=self.company,
            policy=self.policy,
            file_name="test.pdf",
            storage_key="key/test.pdf"
        )

        self.client.force_login(self.user)
        
        # Delete
        response = self.client.delete(f"/api/insurance/documents/{doc.id}/", HTTP_X_TENANT_ID=self.company.tenant_code)
        self.assertEqual(response.status_code, 204)

        # Verify Soft Delete
        doc.refresh_from_db()
        self.assertIsNotNone(doc.deleted_at)

        # Verify List Exclusion
        response = self.client.get(f"/api/insurance/policies/{self.policy.id}/documents/", HTTP_X_TENANT_ID=self.company.tenant_code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_trash_and_restore_document(self):
        doc = PolicyDocument.objects.create(
            company=self.company,
            policy=self.policy,
            file_name="trash_test.pdf",
            storage_key="key/trash_test.pdf",
            deleted_at=timezone.now()
        )

        self.client.force_login(self.user)

        # List Trash
        response = self.client.get("/api/insurance/documents/trash/", HTTP_X_TENANT_ID=self.company.tenant_code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], doc.id)

        # Restore
        response = self.client.post(f"/api/insurance/documents/{doc.id}/restore/", HTTP_X_TENANT_ID=self.company.tenant_code)
        self.assertEqual(response.status_code, 200)
        
        doc.refresh_from_db()
        self.assertIsNone(doc.deleted_at)

        # Verify removed from trash
        response = self.client.get("/api/insurance/documents/trash/", HTTP_X_TENANT_ID=self.company.tenant_code)
        self.assertEqual(len(response.json()), 0)