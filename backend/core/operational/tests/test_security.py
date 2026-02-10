"""Tenant isolation tests for operational views."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import Company
from operational.models import Customer, Lead
from operational.views import TenantScopedAPIViewMixin
from tenancy.context import reset_current_company, set_current_company

User = get_user_model()


class _LeadTestView(TenantScopedAPIViewMixin, APIView):
    model = Lead
    permission_classes = []

    def get(self, request):
        return Response({"ok": True}, status=status.HTTP_200_OK)


class TenantScopedMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.company_a = Company.objects.create(
            name="Company A",
            tenant_code="company-a",
            subdomain="company-a",
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name="Company B",
            tenant_code="company-b",
            subdomain="company-b",
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="user_a",
            email="user_a@test.com",
            password="testpass123",
        )
        self._tenant_token = set_current_company(self.company_a)
        self.lead_a = Lead.objects.create(
            company=self.company_a,
            source="Website",
            full_name="Lead A",
            email="lead_a@test.com",
            phone="11999999999",
            company_name="Company A Lead",
            status=Lead.STATUS_CHOICES[0][0],
        )
        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)
        self.lead_b = Lead.objects.create(
            company=self.company_b,
            source="Import",
            full_name="Lead B",
            email="lead_b@test.com",
            phone="11888888888",
            company_name="Company B Lead",
            status=Lead.STATUS_CHOICES[0][0],
        )
        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_a)

    def tearDown(self):
        reset_current_company(self._tenant_token)
        super().tearDown()

    def test_dispatch_requires_tenant_context(self):
        request = self.factory.get("/api/leads/")
        request.user = self.user
        response = _LeadTestView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dispatch_allows_with_tenant_context(self):
        request = self.factory.get("/api/leads/")
        request.user = self.user
        request.company = self.company_a
        response = _LeadTestView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_queryset_is_tenant_scoped(self):
        request = self.factory.get("/api/leads/")
        request.user = self.user
        request.company = self.company_a
        view = _LeadTestView()
        view.request = request
        qs = view.get_queryset()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.lead_a.pk)

    def test_customer_isolation_by_company(self):
        customer_a = Customer.objects.create(
            company=self.company_a,
            name="Customer A",
            email="customer_a@test.com",
        )
        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_b)
        Customer.objects.create(
            company=self.company_b,
            name="Customer B",
            email="customer_b@test.com",
        )
        reset_current_company(self._tenant_token)
        self._tenant_token = set_current_company(self.company_a)

        class _CustomerView(TenantScopedAPIViewMixin):
            model = Customer

        request = self.factory.get("/api/customers/")
        request.user = self.user
        request.company = self.company_a
        view = _CustomerView()
        view.request = request
        qs = view.get_queryset()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, customer_a.pk)
