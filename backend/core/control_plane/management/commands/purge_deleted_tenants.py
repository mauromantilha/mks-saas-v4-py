from django.core.management.base import BaseCommand

from control_plane.services.data_lifecycle import purge_deleted_tenant_metadata


class Command(BaseCommand):
    help = (
        "Purge metadata for soft-deleted tenants older than retention window. "
        "Default is dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Retention window in days before purge.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes. Without this flag, command runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        result = purge_deleted_tenant_metadata(
            retention_days=options.get("days"),
            apply_changes=options.get("apply", False),
        )
        mode = "APPLY" if options.get("apply") else "DRY-RUN"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] scanned={result.scanned} purged={result.purged}"
            )
        )
