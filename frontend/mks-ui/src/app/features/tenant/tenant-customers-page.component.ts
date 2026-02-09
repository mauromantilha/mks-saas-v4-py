import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import { AIInsightResponse, CustomerRecord } from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-customers-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./tenant-customers-page.component.html",
  styleUrl: "./tenant-customers-page.component.scss",
})
export class TenantCustomersPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  customers = signal<CustomerRecord[]>([]);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  // Create form (minimal; model supports many more fields).
  name = signal("");
  email = signal("");
  cnpj = signal("");
  phone = signal("");
  contactName = signal("");
  industry = signal("");
  leadSource = signal("");
  notes = signal("");

  constructor(
    private readonly salesFlowService: SalesFlowService,
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
    this.salesFlowService.listCustomers().subscribe({
      next: (customers) => {
        this.customers.set(customers);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar clientes."
        );
        this.loading.set(false);
      },
    });
  }

  createCustomer(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const name = this.name().trim();
    const email = this.email().trim();
    if (!name || !email) {
      this.error.set("Nome e email são obrigatórios.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .createCustomer({
        name,
        email,
        cnpj: this.cnpj().trim(),
        phone: this.phone().trim(),
        contact_name: this.contactName().trim(),
        industry: this.industry().trim(),
        lead_source: this.leadSource().trim(),
        notes: this.notes().trim(),
        customer_type: this.cnpj().trim() ? "COMPANY" : "INDIVIDUAL",
        lifecycle_stage: "PROSPECT",
      })
      .subscribe({
        next: (customer) => {
          this.notice.set(`Cliente #${customer.id} criado (IA aplicada automaticamente).`);
          this.resetForm();
          this.load();
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? JSON.stringify(err.error.detail)
              : "Erro ao criar cliente."
          );
          this.loading.set(false);
        },
      });
  }

  resetForm(): void {
    this.name.set("");
    this.email.set("");
    this.cnpj.set("");
    this.phone.set("");
    this.contactName.set("");
    this.industry.set("");
    this.leadSource.set("");
    this.notes.set("");
  }

  generateInsights(customer: CustomerRecord): void {
    this.aiEntityLabel.set(`Cliente #${customer.id}`);
    this.aiResponse.set(null);
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .generateCustomerAIInsights(customer.id, { include_cnpj_enrichment: true })
      .subscribe({
        next: (resp) => {
          this.aiResponse.set(resp);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? JSON.stringify(err.error.detail)
              : "Erro ao gerar insights IA."
          );
          this.loading.set(false);
        },
      });
  }

  enrichCnpj(customer: CustomerRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.enrichCustomerCnpj(customer.id).subscribe({
      next: () => {
        this.notice.set(`CNPJ enriquecido para Cliente #${customer.id}.`);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao enriquecer CNPJ."
        );
        this.loading.set(false);
      },
    });
  }
}

