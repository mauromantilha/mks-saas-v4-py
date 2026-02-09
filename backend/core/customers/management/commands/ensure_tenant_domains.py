from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from customers.models import Company, Domain


class Command(BaseCommand):
    help = "Ensure each tenant has expected Domain mappings (base domain + *.localhost)."

    def handle(self, *args, **options):
        base_domain = getattr(settings, "TENANT_BASE_DOMAIN", "").strip().lower()
        created = 0
        updated_primary = 0

        for company in Company.objects.all().only("id", "subdomain"):
            local_domain = f"{company.subdomain}.localhost"
            _obj, was_created = Domain.objects.get_or_create(
                domain=local_domain,
                defaults={"tenant": company, "is_primary": not bool(base_domain)},
            )
            created += int(was_created)

            if not base_domain:
                continue

            public_domain = f"{company.subdomain}.{base_domain}"
            domain_obj, was_created = Domain.objects.get_or_create(
                domain=public_domain,
                defaults={"tenant": company, "is_primary": True},
            )
            created += int(was_created)

            if not domain_obj.is_primary:
                domain_obj.is_primary = True
                domain_obj.save(update_fields=["is_primary"])
                updated_primary += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"ensure_tenant_domains: created={created}, updated_primary={updated_primary}"
            )
        )

