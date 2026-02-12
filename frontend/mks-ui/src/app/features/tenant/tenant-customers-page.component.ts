import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  AIInsightResponse,
  CepLookupResponse,
  CreateCustomerPayload,
  CreateCustomerContactPayload,
  CustomerContactRecord,
  CustomerLifecycleStage,
  CustomerRecord,
  CustomerType,
  UpdateCustomerPayload,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

type ContactDraft = {
  id?: number;
  name: string;
  email: string;
  phone: string;
  role: string;
  is_primary: boolean;
  notes: string;
};

type CustomerFormModel = {
  customer_type: CustomerType;
  lifecycle_stage: CustomerLifecycleStage;
  name: string;
  email: string;
  cpf: string;
  cnpj: string;
  phone: string;
  whatsapp: string;
  zip_code: string;
  street: string;
  street_number: string;
  address_complement: string;
  neighborhood: string;
  city: string;
  state: string;
  industry: string;
  lead_source: string;
  notes: string;
  contacts: ContactDraft[];
};

@Component({
  selector: "app-tenant-customers-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-customers-page.component.html",
  styleUrl: "./tenant-customers-page.component.scss",
})
export class TenantCustomersPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  readonly industryOptions = [
    { value: "INDUSTRY", label: "Indústria" },
    { value: "COMMERCE", label: "Comércio" },
    { value: "RETAIL", label: "Varejo" },
    { value: "SERVICES", label: "Serviços" },
  ];

  readonly leadSourceOptions = [
    { value: "SOCIAL_MEDIA", label: "Redes Sociais" },
    { value: "GOOGLE_ADS", label: "Google Ads" },
    { value: "FACEBOOK_ADS", label: "Facebook Ads" },
    { value: "OTHER", label: "Outros" },
  ];

  loading = signal(false);
  error = signal("");
  notice = signal("");

  customers = signal<CustomerRecord[]>([]);
  selectedCustomer = signal<CustomerRecord | null>(null);
  editing = signal(false);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  createForm: CustomerFormModel = this.emptyForm("COMPANY");
  editForm: CustomerFormModel = this.emptyForm("COMPANY");

  createCepLoading = signal(false);
  createCepError = signal("");
  editCepLoading = signal(false);
  editCepError = signal("");

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

  private emptyContact(isPrimary = false): ContactDraft {
    return {
      id: undefined,
      name: "",
      email: "",
      phone: "",
      role: "",
      is_primary: isPrimary,
      notes: "",
    };
  }

  private emptyForm(type: CustomerType): CustomerFormModel {
    return {
      customer_type: type,
      lifecycle_stage: "PROSPECT",
      name: "",
      email: "",
      cpf: "",
      cnpj: "",
      phone: "",
      whatsapp: "",
      zip_code: "",
      street: "",
      street_number: "",
      address_complement: "",
      neighborhood: "",
      city: "",
      state: "",
      industry: "",
      lead_source: "",
      notes: "",
      contacts: type === "COMPANY" ? [this.emptyContact(true)] : [],
    };
  }

  private parseApiError(err: unknown, fallback: string): string {
    const e = err as {
      error?: {
        detail?: unknown;
        non_field_errors?: string[];
        [key: string]: unknown;
      };
    };
    const detail = e?.error?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    const nonField = e?.error?.non_field_errors;
    if (Array.isArray(nonField) && nonField.length > 0) {
      return nonField.join(" ");
    }
    if (e?.error && typeof e.error === "object") {
      const messages: string[] = [];
      Object.entries(e.error).forEach(([field, value]) => {
        if (field === "detail") {
          return;
        }
        if (Array.isArray(value)) {
          messages.push(`${field}: ${value.join(" ")}`);
          return;
        }
        if (typeof value === "string") {
          messages.push(`${field}: ${value}`);
        }
      });
      if (messages.length > 0) {
        return messages.join(" | ");
      }
    }
    return fallback;
  }

  private digitsOnly(value: string): string {
    return (value || "").replace(/\D/g, "");
  }

  private isValidCpf(value: string): boolean {
    const cpf = this.digitsOnly(value);
    if (cpf.length !== 11 || /^([0-9])\1+$/.test(cpf)) {
      return false;
    }
    const calc = (base: string, factor: number) => {
      let total = 0;
      for (const digit of base) {
        total += Number(digit) * factor--;
      }
      const mod = (total * 10) % 11;
      return mod === 10 ? 0 : mod;
    };
    const d1 = calc(cpf.slice(0, 9), 10);
    const d2 = calc(cpf.slice(0, 10), 11);
    return d1 === Number(cpf[9]) && d2 === Number(cpf[10]);
  }

  private isValidCnpj(value: string): boolean {
    const cnpj = this.digitsOnly(value);
    if (cnpj.length !== 14 || /^([0-9])\1+$/.test(cnpj)) {
      return false;
    }
    const calc = (base: string, weights: number[]) => {
      const total = base
        .split("")
        .reduce((sum, digit, idx) => sum + Number(digit) * weights[idx], 0);
      const rem = total % 11;
      return rem < 2 ? 0 : 11 - rem;
    };
    const d1 = calc(cnpj.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
    const d2 = calc(cnpj.slice(0, 13), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
    return d1 === Number(cnpj[12]) && d2 === Number(cnpj[13]);
  }

  private hasRequiredFields(form: CustomerFormModel): boolean {
    const baseRequired = [
      form.name,
      form.email,
      form.zip_code,
      form.street,
      form.street_number,
      form.neighborhood,
      form.city,
      form.state,
      form.industry,
      form.lead_source,
    ].every((value) => value.trim().length > 0);

    if (!baseRequired) {
      return false;
    }

    if (form.customer_type === "INDIVIDUAL") {
      return this.isValidCpf(form.cpf);
    }

    if (!this.isValidCnpj(form.cnpj)) {
      return false;
    }

    if (form.contacts.length === 0) {
      return false;
    }

    return form.contacts.every((contact) => {
      const hasName = contact.name.trim().length > 0;
      const hasChannel = contact.email.trim().length > 0 || contact.phone.trim().length > 0;
      return hasName && hasChannel;
    });
  }

  isCreateValid(): boolean {
    return this.hasRequiredFields(this.createForm);
  }

  isEditValid(): boolean {
    return this.hasRequiredFields(this.editForm);
  }

  setCreateType(type: CustomerType): void {
    const contacts = type === "COMPANY" ? this.createForm.contacts : [];
    this.createForm.customer_type = type;
    if (type === "COMPANY" && contacts.length === 0) {
      this.createForm.contacts = [this.emptyContact(true)];
    }
    if (type === "INDIVIDUAL") {
      this.createForm.contacts = [];
      this.createForm.cnpj = "";
    }
    if (type === "COMPANY") {
      this.createForm.cpf = "";
    }
  }

  setEditType(type: CustomerType): void {
    const contacts = type === "COMPANY" ? this.editForm.contacts : [];
    this.editForm.customer_type = type;
    if (type === "COMPANY" && contacts.length === 0) {
      this.editForm.contacts = [this.emptyContact(true)];
    }
    if (type === "INDIVIDUAL") {
      this.editForm.contacts = [];
      this.editForm.cnpj = "";
    }
    if (type === "COMPANY") {
      this.editForm.cpf = "";
    }
  }

  addCreateContact(): void {
    this.createForm.contacts = [...this.createForm.contacts, this.emptyContact(this.createForm.contacts.length === 0)];
  }

  addEditContact(): void {
    this.editForm.contacts = [...this.editForm.contacts, this.emptyContact(this.editForm.contacts.length === 0)];
  }

  removeCreateContact(index: number): void {
    this.createForm.contacts = this.removeContact(this.createForm.contacts, index);
  }

  removeEditContact(index: number): void {
    this.editForm.contacts = this.removeContact(this.editForm.contacts, index);
  }

  private removeContact(list: ContactDraft[], index: number): ContactDraft[] {
    if (index < 0 || index >= list.length) {
      return list;
    }
    const next = list.filter((_item, i) => i !== index);
    if (next.length > 0 && !next.some((item) => item.is_primary)) {
      next[0] = { ...next[0], is_primary: true };
    }
    return next;
  }

  markCreatePrimary(index: number): void {
    this.createForm.contacts = this.markPrimary(this.createForm.contacts, index);
  }

  markEditPrimary(index: number): void {
    this.editForm.contacts = this.markPrimary(this.editForm.contacts, index);
  }

  private markPrimary(list: ContactDraft[], index: number): ContactDraft[] {
    return list.map((item, i) => ({ ...item, is_primary: i === index }));
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.listCustomers().subscribe({
      next: (rows) => {
        this.customers.set(rows);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao carregar clientes."));
        this.loading.set(false);
      },
    });
  }

  lookupCreateCep(): void {
    this.lookupCep(this.createForm.zip_code, (resp) => this.applyCepToForm(this.createForm, resp), this.createCepLoading, this.createCepError);
  }

  lookupEditCep(): void {
    this.lookupCep(this.editForm.zip_code, (resp) => this.applyCepToForm(this.editForm, resp), this.editCepLoading, this.editCepError);
  }

  private lookupCep(
    cepValue: string,
    onSuccess: (resp: CepLookupResponse) => void,
    loadingState: { set(value: boolean): void },
    errorState: { set(value: string): void }
  ): void {
    const cep = this.digitsOnly(cepValue);
    if (!cep) {
      errorState.set("");
      return;
    }
    if (cep.length !== 8) {
      errorState.set("CEP inválido.");
      return;
    }

    loadingState.set(true);
    errorState.set("");

    this.salesFlowService.lookupCep(cep).subscribe({
      next: (resp) => {
        onSuccess(resp);
        loadingState.set(false);
      },
      error: (err) => {
        errorState.set(this.parseApiError(err, "Falha ao consultar CEP."));
        loadingState.set(false);
      },
    });
  }

  private applyCepToForm(form: CustomerFormModel, resp: CepLookupResponse): void {
    form.zip_code = resp.zip_code || form.zip_code;
    form.street = resp.street || form.street;
    form.neighborhood = resp.neighborhood || form.neighborhood;
    form.city = resp.city || form.city;
    form.state = resp.state || form.state;
  }

  private normalizeContacts(list: ContactDraft[]): CreateCustomerContactPayload[] {
    const rows = list
      .map((item) => ({
        id: item.id,
        name: item.name.trim(),
        email: item.email.trim(),
        phone: item.phone.trim(),
        role: item.role.trim(),
        is_primary: item.is_primary,
        notes: item.notes.trim(),
      }))
      .filter((item) => item.name.length > 0);

    if (rows.length > 0 && !rows.some((item) => item.is_primary)) {
      rows[0].is_primary = true;
    }
    return rows;
  }

  private buildPayload(form: CustomerFormModel): UpdateCustomerPayload {
    const contacts = form.customer_type === "COMPANY" ? this.normalizeContacts(form.contacts) : [];
    return {
      name: form.name.trim(),
      email: form.email.trim(),
      customer_type: form.customer_type,
      lifecycle_stage: form.lifecycle_stage,
      document: form.customer_type === "COMPANY" ? form.cnpj.trim() : form.cpf.trim(),
      cnpj: form.customer_type === "COMPANY" ? form.cnpj.trim() : "",
      cpf: form.customer_type === "INDIVIDUAL" ? form.cpf.trim() : "",
      phone: form.phone.trim(),
      whatsapp: form.whatsapp.trim(),
      zip_code: form.zip_code.trim(),
      street: form.street.trim(),
      street_number: form.street_number.trim(),
      address_complement: form.address_complement.trim(),
      neighborhood: form.neighborhood.trim(),
      city: form.city.trim(),
      state: form.state.trim(),
      industry: form.industry.trim(),
      lead_source: form.lead_source.trim(),
      notes: form.notes.trim(),
      contacts,
    };
  }

  private buildCreatePayload(form: CustomerFormModel): CreateCustomerPayload {
    return this.buildPayload(form) as CreateCustomerPayload;
  }

  createCustomer(): void {
    if (!this.canWrite()) {
      this.error.set("Perfil sem permissão de escrita.");
      return;
    }
    if (!this.isCreateValid()) {
      this.error.set("Preencha todos os campos obrigatórios (*). Verifique CPF/CNPJ.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.createCustomer(this.buildCreatePayload(this.createForm)).subscribe({
      next: (row) => {
        this.notice.set(`Cliente criado com sucesso. ID do cliente: #${row.id}.`);
        this.createForm = this.emptyForm("COMPANY");
        this.load();
        this.openCustomer(row.id);
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao criar cliente."));
        this.loading.set(false);
      },
    });
  }

  openCustomer(id: number): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.editing.set(false);

    this.salesFlowService.getCustomer(id).subscribe({
      next: (row) => {
        this.selectedCustomer.set(row);
        this.fillEditForm(row);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao carregar ficha do cliente."));
        this.loading.set(false);
      },
    });
  }

  closeCustomer(): void {
    this.selectedCustomer.set(null);
    this.editing.set(false);
  }

  startEditCustomer(): void {
    const customer = this.selectedCustomer();
    if (!customer) {
      return;
    }
    this.fillEditForm(customer);
    this.editing.set(true);
  }

  cancelEditCustomer(): void {
    const customer = this.selectedCustomer();
    if (customer) {
      this.fillEditForm(customer);
    }
    this.editing.set(false);
  }

  private fillEditForm(customer: CustomerRecord): void {
    const contacts = (customer.contacts ?? []).map((item) => ({
      id: item.id,
      name: item.name || "",
      email: item.email || "",
      phone: item.phone || "",
      role: item.role || "",
      is_primary: item.is_primary,
      notes: item.notes || "",
    }));

    this.editForm = {
      customer_type: customer.customer_type,
      lifecycle_stage: customer.lifecycle_stage,
      name: customer.name || "",
      email: customer.email || "",
      cpf: customer.cpf || "",
      cnpj: customer.cnpj || "",
      phone: customer.phone || "",
      whatsapp: customer.whatsapp || "",
      zip_code: customer.zip_code || "",
      street: customer.street || "",
      street_number: customer.street_number || "",
      address_complement: customer.address_complement || "",
      neighborhood: customer.neighborhood || "",
      city: customer.city || "",
      state: customer.state || "",
      industry: customer.industry || "",
      lead_source: customer.lead_source || "",
      notes: customer.notes || "",
      contacts,
    };

    if (this.editForm.customer_type === "COMPANY" && this.editForm.contacts.length === 0) {
      this.editForm.contacts = [this.emptyContact(true)];
    }
  }

  saveCustomer(): void {
    const customer = this.selectedCustomer();
    if (!customer) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Perfil sem permissão de escrita.");
      return;
    }
    if (!this.isEditValid()) {
      this.error.set("Preencha todos os campos obrigatórios (*). Verifique CPF/CNPJ.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.updateCustomer(customer.id, this.buildPayload(this.editForm)).subscribe({
      next: (row) => {
        this.notice.set(`Cliente #${row.id} atualizado.`);
        this.selectedCustomer.set(row);
        this.editing.set(false);
        this.load();
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao atualizar cliente."));
        this.loading.set(false);
      },
    });
  }

  inactivateCustomer(target?: CustomerRecord): void {
    const customer = target ?? this.selectedCustomer();
    if (!customer || !this.canWrite()) {
      return;
    }
    if (!window.confirm(`Inativar cliente #${customer.id}?`)) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .updateCustomer(customer.id, { lifecycle_stage: "INACTIVE" })
      .subscribe({
        next: (row) => {
          this.notice.set(`Cliente #${row.id} inativado.`);
          if (this.selectedCustomer()?.id === row.id) {
            this.selectedCustomer.set(row);
          }
          this.load();
        },
        error: (err) => {
          this.error.set(this.parseApiError(err, "Erro ao inativar cliente."));
          this.loading.set(false);
        },
      });
  }

  deleteCustomer(target?: CustomerRecord): void {
    const customer = target ?? this.selectedCustomer();
    if (!customer || !this.canWrite()) {
      return;
    }
    if (!window.confirm(`Excluir definitivamente cliente #${customer.id}?`)) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.deleteCustomer(customer.id).subscribe({
      next: () => {
        this.notice.set(`Cliente #${customer.id} excluído.`);
        if (this.selectedCustomer()?.id === customer.id) {
          this.closeCustomer();
        }
        this.load();
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao excluir cliente."));
        this.loading.set(false);
      },
    });
  }

  printCustomerSheet(): void {
    const customer = this.selectedCustomer();
    if (!customer) {
      return;
    }
    const html = `
      <html>
        <head>
          <title>Ficha Cliente #${customer.id}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 24px; color: #111; }
            h1 { margin: 0 0 12px; }
            .meta { margin: 0 0 16px; color: #444; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; }
            p { margin: 0; }
            .section { margin-top: 16px; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
          </style>
        </head>
        <body>
          <h1>Ficha do Cliente #${customer.id}</h1>
          <p class="meta">${customer.name} | ${customer.customer_type} | ${customer.lifecycle_stage}</p>
          <div class="grid">
            <p><strong>Email:</strong> ${customer.email || "-"}</p>
            <p><strong>Telefone:</strong> ${customer.phone || customer.whatsapp || "-"}</p>
            <p><strong>CPF:</strong> ${customer.cpf || "-"}</p>
            <p><strong>CNPJ:</strong> ${customer.cnpj || "-"}</p>
            <p><strong>CEP:</strong> ${customer.zip_code || "-"}</p>
            <p><strong>Cidade/UF:</strong> ${customer.city || "-"}/${customer.state || "-"}</p>
            <p><strong>Bairro:</strong> ${customer.neighborhood || "-"}</p>
            <p><strong>Endereço:</strong> ${customer.street || "-"}, ${customer.street_number || "-"}</p>
            <p><strong>Segmento:</strong> ${customer.industry || "-"}</p>
            <p><strong>Origem:</strong> ${customer.lead_source || "-"}</p>
          </div>
          <div class="section">
            <h3>Contatos</h3>
            <table>
              <thead><tr><th>Nome</th><th>Email</th><th>Telefone</th><th>Cargo</th><th>Primário</th></tr></thead>
              <tbody>
                ${(customer.contacts || [])
                  .map(
                    (c) =>
                      `<tr><td>${c.name || "-"}</td><td>${c.email || "-"}</td><td>${c.phone || "-"}</td><td>${c.role || "-"}</td><td>${c.is_primary ? "Sim" : "Não"}</td></tr>`
                  )
                  .join("") || "<tr><td colspan='5'>Sem contatos</td></tr>"}
              </tbody>
            </table>
          </div>
        </body>
      </html>
    `;

    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      this.error.set("Não foi possível abrir a visualização para impressão.");
      return;
    }
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
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
          this.error.set(this.parseApiError(err, "Erro ao gerar insights IA."));
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
        if (this.selectedCustomer()?.id === customer.id) {
          this.openCustomer(customer.id);
        }
      },
      error: (err) => {
        this.error.set(this.parseApiError(err, "Erro ao enriquecer CNPJ."));
        this.loading.set(false);
      },
    });
  }

  getIndustryLabel(value: string): string {
    return this.industryOptions.find((opt) => opt.value === value)?.label ?? (value || "-");
  }

  getLeadSourceLabel(value: string): string {
    return this.leadSourceOptions.find((opt) => opt.value === value)?.label ?? (value || "-");
  }

  trackContact(_idx: number, contact: CustomerContactRecord): number {
    return contact.id;
  }
}
