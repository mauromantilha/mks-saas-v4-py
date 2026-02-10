from django.core.exceptions import ValidationError
from django.test import TestCase

from commission.models import CommissionPlan, CommissionPlanScope, CommissionSplit
from customers.models import Company
from tenancy.context import reset_current_company, set_current_company


class CommissionModelsIsolationTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Acme",
            tenant_code="acme",
            subdomain="acme",
        )
        self.company_b = Company.objects.create(
            name="Beta",
            tenant_code="beta",
            subdomain="beta",
        )

    def test_manager_fails_closed_without_tenant_context(self):
        CommissionPlan.all_objects.create(company=self.company_a, name="Plan A")
        self.assertEqual(CommissionPlan.objects.count(), 0)

    def test_manager_filters_by_current_company(self):
        token = set_current_company(self.company_a)
        try:
            CommissionPlan.all_objects.create(company=self.company_a, name="Plan A")
        finally:
            reset_current_company(token)

        token = set_current_company(self.company_b)
        try:
            CommissionPlan.all_objects.create(company=self.company_b, name="Plan B")
        finally:
            reset_current_company(token)

        token = set_current_company(self.company_a)
        try:
            self.assertEqual(CommissionPlan.objects.count(), 1)
            self.assertEqual(CommissionPlan.objects.first().name, "Plan A")
        finally:
            reset_current_company(token)

        token = set_current_company(self.company_b)
        try:
            self.assertEqual(CommissionPlan.objects.count(), 1)
            self.assertEqual(CommissionPlan.objects.first().name, "Plan B")
        finally:
            reset_current_company(token)

    def test_cross_tenant_write_is_blocked(self):
        token = set_current_company(self.company_a)
        try:
            with self.assertRaises(ValidationError):
                CommissionPlan.all_objects.create(company=self.company_b, name="Cross")
        finally:
            reset_current_company(token)

    def test_scope_and_split_inherit_company_from_parent(self):
        token = set_current_company(self.company_a)
        try:
            plan = CommissionPlan.all_objects.create(company=self.company_a, name="Plan A")
            scope = CommissionPlanScope.all_objects.create(
                plan=plan,
                company=self.company_a,
                dimension=CommissionPlanScope.Dimension.INSURER,
                value="INS-1",
            )
            split = CommissionSplit.all_objects.create(
                scope=scope,
                company=self.company_a,
                recipient_type=CommissionSplit.RecipientType.ROLE,
                recipient_ref="OWNER",
                percentage="60.00",
            )
        finally:
            reset_current_company(token)
        self.assertEqual(scope.company_id, plan.company_id)
        self.assertEqual(split.company_id, scope.company_id)
