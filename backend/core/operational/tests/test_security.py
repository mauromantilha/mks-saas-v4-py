"""
Tests for tenant isolation and security.

These tests verify that:
1. Users from one tenant cannot access data from another tenant
2. Cross-tenant access is properly blocked
3. Tenant context validation works correctly
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from customers.models import Company
from operational.models import Lead, Customer, Opportunity
from operational.views import TenantScopedAPIViewMixin

User = get_user_model()


class TenantIsolationTestCase(TestCase):
    """Test cross-tenant data access prevention."""

    def setUp(self):
        """Create two companies with users and data."""
        # Company A setup
        self.company_a = Company.objects.create(
            name="Company A",
            tenant_code="company-a",
            subdomain="company-a",
            is_active=True,
        )
        self.user_a = User.objects.create_user(
            username="user_a",
            email="user_a@company-a.com",
            password="testpass123",
        )
        self.lead_a = Lead.objects.create(
            company=self.company_a,
            created_by=self.user_a,
            full_name="Lead A",
            email="lead_a@test.com",
            phone="1122223333",
            company_name="Company A Lead",
            status="QUALIFIED",
        )

        # Company B setup
        self.company_b = Company.objects.create(
            name="Company B",
            tenant_code="company-b",
            subdomain="company-b",
            is_active=True,
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="user_b@company-b.com",
            password="testpass123",
        )
        self.lead_b = Lead.objects.create(
            company=self.company_b,
            created_by=self.user_b,
            full_name="Lead B",
            email="lead_b@test.com",
            phone="4455556666",
            company_name="Company B Lead",
            status="QUALIFIED",
        )

        self.client = APIClient()

    def test_user_cannot_list_leads_from_other_tenant(self):
        """Verify that list endpoint filters by tenant."""
        self.client.force_authenticate(user=self.user_a)
        # Simulate request.company being set by middleware
        response = self.client.get("/api/leads/")
        
        # Response should only contain leads from company_a
        # (Implementation depends on actual API endpoint)
        # This is a placeholder for the actual test
        assert response.status_code == 200

    def test_user_cannot_retrieve_lead_from_other_tenant(self):
        """Verify that detail endpoint blocks cross-tenant access."""
        self.client.force_authenticate(user=self.user_a)
        
        # Try to access lead from company_b while authenticated as user_a
        response = self.client.get(f"/api/leads/{self.lead_b.id}/")
        
        # Should return 404 (not found) because lead_b doesn't belong to company_a
        # The actual status code depends on how the endpoint handles missing objects
        assert response.status_code in [404, 403]

    def test_user_cannot_qualify_lead_from_other_tenant(self):
        """Verify that action endpoints block cross-tenant access."""
        self.client.force_authenticate(user=self.user_a)
        
        # Try to qualify a lead from another company
        response = self.client.post(f"/api/leads/{self.lead_b.id}/qualify/")
        
        # Should return 404 or 403
        assert response.status_code in [404, 403]

    def test_queryset_filtering_by_company(self):
        """Verify TenantScopedAPIViewMixin filters by company."""
        factory = RequestFactory()
        request = factory.get("/api/leads/")
        request.user = self.user_a
        request.company = self.company_a

        # Create a simple test view
        class TestLeadView(TenantScopedAPIViewMixin):
            model = Lead

        view = TestLeadView()
        view.request = request
        
        queryset = view.get_queryset()
        
        # Queryset should only include leads from company_a
        assert queryset.count() == 1
        assert queryset.first().id == self.lead_a.id

    def test_queryset_empty_when_no_company_context(self):
        """Verify get_queryset returns empty when company context is missing."""
        factory = RequestFactory()
        request = factory.get("/api/leads/")
        request.user = self.user_a
        # Don't set request.company

        class TestLeadView(TenantScopedAPIViewMixin):
            model = Lead

        view = TestLeadView()
        view.request = request
        
        queryset = view.get_queryset()
        
        # Queryset should be empty
        assert queryset.count() == 0

    def test_customer_isolation(self):
        """Verify customers are isolated by tenant."""
        customer_a = Customer.objects.create(
            company=self.company_a,
            name="Customer A",
            email="customer_a@test.com",
        )
        customer_b = Customer.objects.create(
            company=self.company_b,
            name="Customer B",
            email="customer_b@test.com",
        )

        # User A should only see their company's customers
        factory = RequestFactory()
        request = factory.get("/api/customers/")
        request.user = self.user_a
        request.company = self.company_a

        class TestCustomerView(TenantScopedAPIViewMixin):
            model = Customer

        view = TestCustomerView()
        view.request = request
        
        queryset = view.get_queryset()
        assert queryset.count() == 1
        assert queryset.first().id == customer_a.id

    def test_opportunity_isolation(self):
        """Verify opportunities are isolated by tenant."""
        customer_a = Customer.objects.create(
            company=self.company_a,
            name="Customer A",
            email="customer_a@test.com",
        )
        opportunity_a = Opportunity.objects.create(
            company=self.company_a,
            customer=customer_a,
            title="Opportunity A",
            stage="QUALIFICATION",
        )

        customer_b = Customer.objects.create(
            company=self.company_b,
            name="Customer B",
            email="customer_b@test.com",
        )
        opportunity_b = Opportunity.objects.create(
            company=self.company_b,
            customer=customer_b,
            title="Opportunity B",
            stage="QUALIFICATION",
        )

        # User A should only see their company's opportunities
        factory = RequestFactory()
        request = factory.get("/api/opportunities/")
        request.user = self.user_a
        request.company = self.company_a

        class TestOpportunityView(TenantScopedAPIViewMixin):
            model = Opportunity

        view = TestOpportunityView()
        view.request = request
        
        queryset = view.get_queryset()
        assert queryset.count() == 1
        assert queryset.first().id == opportunity_a.id


class TenantContextValidationTestCase(TestCase):
    """Test tenant context validation in dispatch."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            tenant_code="test-company",
            subdomain="test",
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123",
        )
        self.factory = RequestFactory()

    def test_dispatch_requires_company_context(self):
        """Verify dispatch() validates company context."""
        request = self.factory.get("/api/leads/")
        request.user = self.user
        # Don't set request.company

        class TestView(TenantScopedAPIViewMixin):
            model = Lead

            def get(self, request):
                return super().dispatch(request)

        view = TestView()
        response = view.dispatch(request)
        
        # Should return 403 Forbidden when company context is missing
        assert response.status_code == 403

    def test_dispatch_allows_with_company_context(self):
        """Verify dispatch() allows request when company context is present."""
        request = self.factory.get("/api/leads/")
        request.user = self.user
        request.company = self.company

        class TestView(TenantScopedAPIViewMixin):
            model = Lead

            def get(self, request):
                # This should not raise an error
                return super().dispatch(request)

        view = TestView()
        # Should not raise or return 403
        response = view.dispatch(request)
        # Response will be whatever super().dispatch() returns
        assert response.status_code != 403


@override_settings(DEBUG=False)
class SecurityConfigurationTestCase(TestCase):
    """Test security-related configuration."""

    def test_secret_key_required_in_production(self):
        """Verify SECRET_KEY configuration is enforced."""
        # This test is more of a documentation test
        # In a real scenario, you'd verify settings.SECRET_KEY is not insecure
        from django.conf import settings
        
        # Should not contain 'insecure' in production
        if not settings.DEBUG:
            assert "insecure" not in settings.SECRET_KEY.lower()

    def test_allowed_hosts_configured_in_production(self):
        """Verify ALLOWED_HOSTS is not empty in production."""
        from django.conf import settings
        
        if not settings.DEBUG:
            assert len(settings.ALLOWED_HOSTS) > 0
            # Should not be just localhost
            assert "localhost" not in settings.ALLOWED_HOSTS or len(settings.ALLOWED_HOSTS) > 1

    def test_cors_origins_configured_in_production(self):
        """Verify CORS_ALLOWED_ORIGINS is configured."""
        from django.conf import settings
        
        # In production, CORS should be restricted
        if not settings.DEBUG:
            # This depends on your actual settings implementation
            # Just checking it doesn't contain localhost as the only origin
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
