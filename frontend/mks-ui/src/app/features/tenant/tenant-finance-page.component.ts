import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";

import { FinanceService } from "../../core/api/finance.service";
import {
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

  invoices = signal<ReceivableInvoiceRecord[]>([]);
  statusFilter = signal<ReceivableInvoiceStatus | "">("");
  search = signal("");
  expandedInvoiceId = signal<number | null>(null);

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

    this.financeService.listInvoices().subscribe({
      next: (rows) => {
        this.invoices.set(rows);
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

  installmentStatusLabel(status: ReceivableInstallmentRecord["status"]): string {
    if (status === "OPEN") {
      return "Aberta";
    }
    if (status === "PAID") {
      return "Paga";
    }
    return "Cancelada";
  }

  private toNumber(value: string | number | null | undefined): number {
    const parsed = typeof value === "number" ? value : Number(value ?? 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }
}
