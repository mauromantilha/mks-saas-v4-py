from django.conf import settings
from django.db import models
from tenancy.models import BaseTenantModel


class IntegrationInbox(BaseTenantModel):
    event_id = models.CharField(max_length=120)
    event_type = models.CharField(max_length=120)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "event_id"),
                name="uq_finance_inbox_event_id_company",
            ),
        ]


class Payable(BaseTenantModel):
    STATUS_OPEN = "OPEN"
    STATUS_PAID = "PAID"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_PAID, "Pago"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="payables",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    beneficiary_name = models.CharField(max_length=255, blank=True, help_text="For external payees (e.g. Insurers)")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    source_ref = models.CharField(max_length=100, blank=True, help_text="Reference to source document (e.g. Batch ID)")

    class Meta:
        app_label = "finance"
        ordering = ("due_date",)

    def __str__(self):
        name = self.beneficiary_name or (self.recipient.username if self.recipient else "Unknown")
        return f"Payable {self.id} - {name} - {self.amount}"


class ReceivableInvoice(BaseTenantModel):
    STATUS_OPEN = "OPEN"
    STATUS_PAID = "PAID"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_PAID, "Pago"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    payer = models.ForeignKey(
        "operational.Customer",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    policy = models.ForeignKey(
        "insurance_core.Policy",
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True,
    )
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    issue_date = models.DateField()
    description = models.CharField(max_length=255)

    class Meta:
        app_label = "finance"
        ordering = ("-issue_date",)

    def __str__(self):
        return f"Invoice {self.id} - {self.payer} - {self.total_amount}"


class ReceivableInstallment(BaseTenantModel):
    STATUS_OPEN = "OPEN"
    STATUS_PAID = "PAID"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Aberto"),
        (STATUS_PAID, "Pago"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    invoice = models.ForeignKey(ReceivableInvoice, on_delete=models.CASCADE, related_name="installments")
    number = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "finance"
        ordering = ("due_date", "number")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "invoice", "number"),
                name="uq_receivable_installment_number",
            ),
        ]
