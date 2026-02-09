import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  AIInsightResponse,
  CreateCustomerContactPayload,
  CustomerRecord,
  CustomerType,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

type ContactDraft = {
  name: string;
  email: string;
  phone: string;
  role: string;
  is_primary: boolean;
  notes: string;
};

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
  readonly isCompany = computed(() => this.customerType() === "COMPANY");

  loading = signal(false);
  error = signal("");
  notice = signal("");

  customers = signal<CustomerRecord[]>([]);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  // Create form (complete enough for operational use).
  customerType = signal<CustomerType>("COMPANY");
  name = signal("");
  email = signal("");
  cpf = signal("");
  cnpj = signal("");
  phone = signal("");
  whatsapp = signal("");

  zipCode = signal("");
  street = signal("");
  streetNumber = signal("");
  addressComplement = signal("");
  neighborhood = signal("");
  city = signal("");
  state = signal("");

  contacts = signal<ContactDraft[]>([]);
  cepLoading = signal(false);
  cepError = signal("");

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

  private digitsOnly(value: string): string {
    return (value || "").replace(/\D/g, "");
  }

  private blankContact(isPrimary = false): ContactDraft {
    return {
      name: "",
      email: "",
      phone: "",
      role: "",
      is_primary: isPrimary,
      notes: "",
    };
  }

  setCustomerType(value: CustomerType): void {
    this.customerType.set(value);
    this.cepError.set("");
    if (value === "COMPANY" && this.contacts().length === 0) {
      this.contacts.set([this.blankContact(true)]);
    }
    if (value === "INDIVIDUAL") {
      this.contacts.set([]);
    }
  }

  addContact(): void {
    const next = [...this.contacts(), this.blankContact(this.contacts().length === 0)];
    this.contacts.set(next);
  }

  removeContact(index: number): void {
    const rows = this.contacts();
    if (index < 0 || index >= rows.length) {
      return;
    }
    const next = rows.filter((_row, i) => i !== index);
    if (next.length > 0 && !next.some((c) => c.is_primary)) {
      next[0] = { ...next[0], is_primary: true };
    }
    this.contacts.set(next);
  }

  markPrimary(index: number): void {
    const rows = this.contacts();
    const next = rows.map((row, i) => ({ ...row, is_primary: i === index }));
    this.contacts.set(next);
  }

  updateContact(index: number, key: keyof ContactDraft, value: string): void {
    const rows = this.contacts();
    if (index < 0 || index >= rows.length) {
      return;
    }
    const next = rows.map((row, i) => (i === index ? { ...row, [key]: value } : row));
    this.contacts.set(next);
  }

  lookupCep(): void {
    const raw = this.zipCode().trim();
    const cep = this.digitsOnly(raw);
    if (!cep) {
      this.cepError.set("");
      return;
    }
    if (cep.length !== 8) {
      this.cepError.set("CEP inválido. Informe 8 dígitos.");
      return;
    }

    this.cepLoading.set(true);
    this.cepError.set("");

    this.salesFlowService.lookupCep(cep).subscribe({
      next: (resp) => {
        this.zipCode.set(resp.zip_code || raw);
        this.street.set(resp.street || this.street());
        this.neighborhood.set(resp.neighborhood || this.neighborhood());
        this.city.set(resp.city || this.city());
        this.state.set(resp.state || this.state());
        this.cepLoading.set(false);
      },
      error: (err) => {
        this.cepError.set(
          err?.error?.detail ? String(err.error.detail) : "Falha ao consultar CEP."
        );
        this.cepLoading.set(false);
      },
    });
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

    const customerType = this.customerType();
    const cpf = this.cpf().trim();
    const cnpj = this.cnpj().trim();
    if (customerType === "INDIVIDUAL" && !cpf) {
      this.error.set("CPF é obrigatório para Pessoa Física.");
      return;
    }
    if (customerType === "COMPANY" && !cnpj) {
      this.error.set("CNPJ é obrigatório para Pessoa Jurídica.");
      return;
    }

    const zipCode = this.zipCode().trim();
    const street = this.street().trim();
    const streetNumber = this.streetNumber().trim();
    const neighborhood = this.neighborhood().trim();
    const city = this.city().trim();
    const state = this.state().trim();

    if (!zipCode || !street || !streetNumber || !neighborhood || !city || !state) {
      this.error.set(
        "Endereço incompleto. Informe CEP, logradouro, número, bairro, cidade e UF."
      );
      return;
    }

    let contacts: CreateCustomerContactPayload[] | undefined;
    if (customerType === "COMPANY") {
      const raw = this.contacts();
      const normalized = raw
        .map((c) => ({
          name: c.name.trim(),
          email: c.email.trim(),
          phone: c.phone.trim(),
          role: c.role.trim(),
          is_primary: c.is_primary,
          notes: c.notes.trim(),
        }))
        .filter((c) => c.name);

      if (normalized.length === 0) {
        this.error.set("Informe pelo menos um contato (nome).");
        return;
      }

      if (!normalized.some((c) => c.is_primary)) {
        normalized[0].is_primary = true;
      }

      const invalidContact = normalized.find((c) => !c.email && !c.phone);
      if (invalidContact) {
        this.error.set("Cada contato deve ter ao menos email ou telefone.");
        return;
      }

      contacts = normalized;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .createCustomer({
        name,
        email,
        customer_type: customerType,
        lifecycle_stage: "PROSPECT",
        document: customerType === "COMPANY" ? cnpj : cpf,
        cnpj: customerType === "COMPANY" ? cnpj : "",
        cpf: customerType === "INDIVIDUAL" ? cpf : "",
        phone: this.phone().trim(),
        whatsapp: this.whatsapp().trim(),
        zip_code: zipCode,
        street,
        street_number: streetNumber,
        address_complement: this.addressComplement().trim(),
        neighborhood,
        city,
        state,
        industry: this.industry().trim(),
        lead_source: this.leadSource().trim(),
        notes: this.notes().trim(),
        contacts,
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
    this.customerType.set("COMPANY");
    this.name.set("");
    this.email.set("");
    this.cpf.set("");
    this.cnpj.set("");
    this.phone.set("");
    this.whatsapp.set("");
    this.zipCode.set("");
    this.street.set("");
    this.streetNumber.set("");
    this.addressComplement.set("");
    this.neighborhood.set("");
    this.city.set("");
    this.state.set("");
    this.contacts.set([]);
    this.cepLoading.set(false);
    this.cepError.set("");
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
