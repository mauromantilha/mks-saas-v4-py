import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { forkJoin } from "rxjs";

import { FinanceService } from "../../core/api/finance.service";
import {
  PayableRecord,
  PayableStatus,
  ReceivableInstallmentStatus,
  ReceivableInstallmentRecord,
  ReceivableInvoiceRecord,
  ReceivableInvoiceStatus,
} from "../../core/api/finance.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-finance-page",
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: "./tenant-finance-page.component.html",
  styleUrl: "./tenant-finance-page.component.scss",
})
export class TenantFinancePageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  readonly session = computed(() => this.sessionService.session());

  loading = signal(false);
  error = signal("");
  notice = signal("");

  activeSection = signal<"receivables" | "payables" | "installments">("receivables");

  invoices = signal<ReceivableInvoiceRecord[]>([]);
  payables = signal<PayableRecord[]>([]);
  installments = signal<ReceivableInstallmentRecord[]>([]);
  statusFilter = signal<ReceivableInvoiceStatus | "">("");
  search = signal("");
  expandedInvoiceId = signal<number | null>(null);
  installmentStatusFilter = signal<ReceivableInstallmentStatus | "DELINQUENT" | "">("");
  installmentPolicyFilter = signal<number | null>(null);
  installmentInsurerFilter = signal<number | null>(null);
  installmentsOnlyDelinquent = signal(false);
  settlingInstallmentId = signal<number | null>(null);

  readonly filteredInvoices = computed(() => {
    const status = this.statusFilter();
    const search = this.search().trim().toLowerCase();
    return this.invoices().filter((invoice) => {
      if (status && invoice.status !== status) {
        return false;
      }
      if (!search) {
        return true;
      }
      const searchable = [
        String(invoice.id),
        invoice.payer_name ?? "",
        invoice.policy_number ?? "",
        invoice.description ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return searchable.includes(search);
    });
  });

  readonly filteredPayables = computed(() => this.payables());
  readonly filteredInstallments = computed(() => this.installments());

  readonly installmentPolicies = computed(() => {
    const entries = new Map<number, string>();
    this.installments().forEach((installment) => {
      if (!installment.policy_id) {
        return;
      }
      entries.set(
        installment.policy_id,
        installment.policy_number || `#${installment.policy_id}`
      );
    });
    return Array.from(entries.entries())
      .map(([id, label]) => ({ id, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  });

  readonly installmentInsurers = computed(() => {
    const entries = new Map<number, string>();
    this.installments().forEach((installment) => {
      if (!installment.insurer_id) {
        return;
      }
      entries.set(installment.insurer_id, installment.insurer_name || `#${installment.insurer_id}`);
    });
    return Array.from(entries.entries())
      .map(([id, label]) => ({ id, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  });

  readonly openAmount = computed(() =>
    this.filteredInvoices()
      .filter((invoice) => invoice.status === "OPEN")
      .reduce((total, row) => total + this.toNumber(row.total_amount), 0)
  );

  readonly paidAmount = computed(() =>
    this.filteredInvoices()
      .filter((invoice) => invoice.status === "PAID")
      .reduce((total, row) => total + this.toNumber(row.total_amount), 0)
  );

  readonly overdueInstallments = computed(() => {
    const today = new Date();
    let overdueCount = 0;
    let overdueAmount = 0;
    this.filteredInvoices().forEach((invoice) => {
      invoice.installments.forEach((installment) => {
        if (installment.status !== "OPEN") {
          return;
        }
        const dueDate = new Date(installment.due_date);
        if (Number.isNaN(dueDate.getTime())) {
          return;
        }
        if (dueDate < today) {
          overdueCount += 1;
          overdueAmount += this.toNumber(installment.amount);
        }
      });
    });
    return { overdueCount, overdueAmount };
  });

  readonly payablesOpenAmount = computed(() =>
    this.filteredPayables()
      .filter((payable) => payable.status === "OPEN")
      .reduce((total, payable) => total + this.toNumber(payable.amount), 0)
  );

  readonly payablesOverdueAmount = computed(() =>
    this.filteredPayables()
      .filter((payable) => payable.is_overdue)
      .reduce((total, payable) => total + this.toNumber(payable.amount), 0)
  );

  readonly installmentsOpenAmount = computed(() =>
    this.filteredInstallments()
      .filter((installment) => installment.status === "OPEN")
      .reduce((total, installment) => total + this.toNumber(installment.amount), 0)
  );

  readonly installmentsOverdueAmount = computed(() =>
    this.filteredInstallments()
      .filter((installment) => installment.is_overdue)
      .reduce((total, installment) => total + this.toNumber(installment.amount), 0)
  );

  constructor(
    private readonly financeService: FinanceService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    forkJoin({
      invoices: this.financeService.listInvoices(),
      payables: this.financeService.listPayables(),
      installments: this.financeService.listInstallments(),
    }).subscribe({
      next: ({ invoices, payables, installments }) => {
        this.invoices.set(invoices);
        this.payables.set(payables);
        this.installments.set(installments);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? String(err.error.detail)
            : "Erro ao carregar recebíveis do tenant."
        );
        this.loading.set(false);
      },
    });
  }

  toggleInvoiceDetails(invoiceId: number): void {
    this.expandedInvoiceId.set(this.expandedInvoiceId() === invoiceId ? null : invoiceId);
  }

  isExpanded(invoiceId: number): boolean {
    return this.expandedInvoiceId() === invoiceId;
  }

  setSection(section: "receivables" | "payables" | "installments"): void {
    this.activeSection.set(section);
  }

  applyInstallmentFilters(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.financeService
      .listInstallments({
        policy_id: this.installmentPolicyFilter(),
        insurer_id: this.installmentInsurerFilter(),
        status: this.installmentStatusFilter(),
        delinquent_only: this.installmentsOnlyDelinquent(),
      })
      .subscribe({
        next: (rows) => {
          this.installments.set(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? String(err.error.detail)
              : "Erro ao aplicar filtros de parcelas."
          );
          this.loading.set(false);
        },
      });
  }

  clearInstallmentFilters(): void {
    this.installmentStatusFilter.set("");
    this.installmentPolicyFilter.set(null);
    this.installmentInsurerFilter.set(null);
    this.installmentsOnlyDelinquent.set(false);
    this.applyInstallmentFilters();
  }

  settleInstallment(installment: ReceivableInstallmentRecord): void {
    if (installment.status !== "OPEN") {
      this.notice.set("Apenas parcelas em aberto podem ser baixadas.");
      return;
    }

    const confirmed = window.confirm(
      `Confirmar baixa da parcela #${installment.number} da fatura #${installment.invoice_id}?`
    );
    if (!confirmed) {
      return;
    }

    this.settlingInstallmentId.set(installment.id);
    this.error.set("");
    this.notice.set("");
    this.financeService.settleInstallment(installment.id).subscribe({
      next: () => {
        this.notice.set("Parcela baixada com sucesso.");
        this.settlingInstallmentId.set(null);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? String(err.error.detail)
            : "Erro ao dar baixa na parcela."
        );
        this.settlingInstallmentId.set(null);
      },
    });
  }

  formatCurrency(value: string | number | null | undefined): string {
    return this.brlFormatter.format(this.toNumber(value));
  }

  statusLabel(status: ReceivableInvoiceStatus): string {
    if (status === "OPEN") {
      return "Aberto";
    }
    if (status === "PAID") {
      return "Pago";
    }
    return "Cancelado";
  }

  payableStatusLabel(status: PayableStatus): string {
    if (status === "OPEN") {
      return "Aberto";
    }
    if (status === "PAID") {
      return "Pago";
    }
    return "Cancelado";
  }

  installmentStatusLabel(status: ReceivableInstallmentRecord["status"]): string {
    if (status === "OPEN") {
      return "Aberta";
    }
    if (status === "PAID") {
      return "Paga";
    }
    return "Cancelada";
  }

  parseOptionalNumber(value: unknown): number | null {
    const parsed = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return null;
    }
    return parsed;
  }

  private toNumber(value: string | number | null | undefined): number {
    const parsed = typeof value === "number" ? value : Number(value ?? 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }
}
