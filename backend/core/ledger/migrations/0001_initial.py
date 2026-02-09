# Generated manually (no network in Codex sandbox). Keep in sync with ledger/models.py.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("customers", "0004_alter_company_rbac_overrides"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(choices=[("TENANT", "Tenant"), ("PLATFORM", "Platform")], default="TENANT", max_length=20)),
                ("actor_username", models.CharField(blank=True, max_length=150)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                ("action", models.CharField(choices=[("CREATE", "Create"), ("UPDATE", "Update"), ("DELETE", "Delete"), ("SYSTEM", "System")], default="SYSTEM", max_length=20)),
                ("event_type", models.CharField(blank=True, max_length=120)),
                ("resource_label", models.CharField(max_length=200)),
                ("resource_pk", models.CharField(blank=True, max_length=64)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("request_id", models.UUIDField(blank=True, null=True)),
                ("request_method", models.CharField(blank=True, max_length=12)),
                ("request_path", models.CharField(blank=True, max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("chain_id", models.CharField(db_index=True, max_length=80)),
                ("prev_hash", models.CharField(blank=True, default="", max_length=64)),
                ("entry_hash", models.CharField(max_length=64, unique=True)),
                ("data_before", models.JSONField(blank=True, null=True)),
                ("data_after", models.JSONField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ledger_entries", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="customers.company")),
            ],
            options={
                "verbose_name": "Ledger Entry",
                "verbose_name_plural": "Ledger Entries",
                "ordering": ("-occurred_at", "-id"),
            },
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.CheckConstraint(
                check=models.Q(("scope", "TENANT"), ("company__isnull", False))
                | models.Q(("scope", "PLATFORM"), ("company__isnull", True)),
                name="ck_ledger_scope_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.UniqueConstraint(fields=("chain_id", "prev_hash"), name="uq_ledger_prev_hash_per_chain"),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.UniqueConstraint(fields=("chain_id", "entry_hash"), name="uq_ledger_entry_hash_per_chain"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=("chain_id", "occurred_at"), name="idx_ledger_chain_occurred"),
        ),
    ]

