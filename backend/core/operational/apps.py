from django.apps import AppConfig


class OperationalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'operational'

    def ready(self):
        # Register signal handlers for IA document indexing hooks.
        from operational import signals  # noqa: F401
