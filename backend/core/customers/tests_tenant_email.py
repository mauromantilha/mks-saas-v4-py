from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase, override_settings

from customers.models import Company, CompanyMembership, TenantEmailConfig
from customers.services import EmailService, TenantEmailServiceError


class TenantEmailConfigAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="email-owner",
            password="test-pass-123",
            email="owner@test.com",
        )
        self.manager = User.objects.create_user(
            username="email-manager",
            password="test-pass-456",
            email="manager@test.com",
        )
        self.company = Company.objects.create(
            name="Email Tenant",
            tenant_code="email-tenant",
            subdomain="email-tenant",
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.owner,
            role=CompanyMembership.ROLE_OWNER,
        )
        CompanyMembership.objects.create(
            company=self.company,
            user=self.manager,
            role=CompanyMembership.ROLE_MANAGER,
        )

    def _payload(self):
        return {
            "smtp_host": "smtp.mail.local",
            "smtp_port": 587,
            "smtp_username": "mailer",
            "smtp_password": "secret",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
            "default_from_email": "no-reply@email-tenant.com",
            "default_from_name": "Email Tenant",
            "reply_to_email": "support@email-tenant.com",
            "is_enabled": True,
        }

    def test_owner_can_create_and_get_email_config(self):
        self.client.force_login(self.owner)

        create_response = self.client.post(
            "/api/admin/email-config/",
            data=self._payload(),
            content_type="application/json",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.json()
        self.assertEqual(create_payload["tenant_code"], "email-tenant")
        self.assertTrue(create_payload["config"]["has_smtp_password"])
        self.assertNotIn("smtp_password", create_payload["config"])

        config = TenantEmailConfig.objects.get(company=self.company)
        self.assertEqual(config.smtp_host, "smtp.mail.local")

        get_response = self.client.get(
            "/api/admin/email-config/",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(get_response.status_code, 200)
        get_payload = get_response.json()
        self.assertEqual(get_payload["config"]["smtp_host"], "smtp.mail.local")

    def test_manager_cannot_manage_email_config(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            "/api/admin/email-config/",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(response.status_code, 403)

    @patch("customers.views.EmailService.send_email", return_value=1)
    def test_test_endpoint_updates_status_success(self, _send_email):
        TenantEmailConfig.objects.create(company=self.company, **self._payload())
        self.client.force_login(self.owner)

        response = self.client.post(
            "/api/admin/email-config/test/",
            data={"to_email": "destino@test.com"},
            content_type="application/json",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["last_test_status"], TenantEmailConfig.TEST_STATUS_SUCCESS)

        config = TenantEmailConfig.objects.get(company=self.company)
        self.assertEqual(config.last_test_status, TenantEmailConfig.TEST_STATUS_SUCCESS)
        self.assertIsNotNone(config.last_tested_at)

    @patch("customers.views.EmailService.send_email", side_effect=TenantEmailServiceError("smtp error"))
    def test_test_endpoint_updates_status_failed(self, _send_email):
        TenantEmailConfig.objects.create(company=self.company, **self._payload())
        self.client.force_login(self.owner)

        response = self.client.post(
            "/api/admin/email-config/test/",
            data={"to_email": "destino@test.com"},
            content_type="application/json",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(response.status_code, 400)

        config = TenantEmailConfig.objects.get(company=self.company)
        self.assertEqual(config.last_test_status, TenantEmailConfig.TEST_STATUS_FAILED)
        self.assertIsNotNone(config.last_tested_at)

    def test_capabilities_include_tenant_email_manage(self):
        self.client.force_login(self.owner)
        owner_response = self.client.get(
            "/api/auth/capabilities/",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(owner_response.status_code, 200)
        owner_caps = owner_response.json()["capabilities"]
        self.assertTrue(owner_caps["tenant.email.manage"]["list"])
        self.assertTrue(owner_caps["tenant.email.manage"]["create"])

        self.client.force_login(self.manager)
        manager_response = self.client.get(
            "/api/auth/capabilities/",
            HTTP_X_TENANT_ID="email-tenant",
        )
        self.assertEqual(manager_response.status_code, 200)
        manager_caps = manager_response.json()["capabilities"]
        self.assertFalse(manager_caps["tenant.email.manage"]["list"])
        self.assertFalse(manager_caps["tenant.email.manage"]["create"])


class EmailServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Service Tenant",
            tenant_code="service-tenant",
            subdomain="service-tenant",
        )

    @patch("customers.services.email_service.EmailMultiAlternatives")
    @patch("customers.services.email_service.get_connection")
    def test_send_email_uses_tenant_smtp_config(self, mock_get_connection, mock_message_cls):
        TenantEmailConfig.objects.create(
            company=self.company,
            smtp_host="smtp.tenant.local",
            smtp_port=2525,
            smtp_username="tenant-user",
            smtp_password="tenant-pass",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            default_from_email="no-reply@tenant.local",
            default_from_name="Tenant Sender",
            reply_to_email="reply@tenant.local",
            is_enabled=True,
        )
        message = mock_message_cls.return_value
        message.send.return_value = 1

        sent = EmailService().send_email(
            company=self.company,
            to_list=["customer@test.com"],
            subject="Subject",
            text="Plain text",
            html="<p>HTML</p>",
        )

        self.assertEqual(sent, 1)
        mock_get_connection.assert_called_once_with(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host="smtp.tenant.local",
            port=2525,
            username="tenant-user",
            password="tenant-pass",
            use_tls=True,
            use_ssl=False,
            fail_silently=False,
        )
        message.send.assert_called_once_with(fail_silently=False)

    @override_settings(
        TENANT_EMAIL_ALLOW_GLOBAL_FALLBACK=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="global@test.com",
    )
    @patch("customers.services.email_service.EmailMultiAlternatives")
    @patch("customers.services.email_service.get_connection")
    def test_send_email_uses_global_fallback_when_config_missing(
        self,
        mock_get_connection,
        mock_message_cls,
    ):
        message = mock_message_cls.return_value
        message.send.return_value = 1

        sent = EmailService().send_email(
            company=self.company,
            to_list=["customer@test.com"],
            subject="Subject",
            text="Plain text",
            html="",
        )

        self.assertEqual(sent, 1)
        mock_get_connection.assert_called_once_with(
            backend="django.core.mail.backends.locmem.EmailBackend",
            host=getattr(settings, "EMAIL_HOST", None),
            port=getattr(settings, "EMAIL_PORT", None),
            username=getattr(settings, "EMAIL_HOST_USER", None),
            password=getattr(settings, "EMAIL_HOST_PASSWORD", None),
            use_tls=bool(getattr(settings, "EMAIL_USE_TLS", False)),
            use_ssl=bool(getattr(settings, "EMAIL_USE_SSL", False)),
            fail_silently=False,
        )

    @override_settings(TENANT_EMAIL_ALLOW_GLOBAL_FALLBACK=False)
    def test_send_email_rejects_when_config_missing_and_fallback_disabled(self):
        with self.assertRaises(TenantEmailServiceError):
            EmailService().send_email(
                company=self.company,
                to_list=["customer@test.com"],
                subject="Subject",
                text="Plain text",
                html="",
            )
