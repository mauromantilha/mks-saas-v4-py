from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "customers"

    def ready(self):
        # Register signal handlers (guardian integration is conditional).
        from customers import signals  # noqa: F401
