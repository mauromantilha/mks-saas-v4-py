import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { InsuranceCoreService } from "../../core/api/insurance-core.service";
import {
  CreateEndorsementPayload,
  CreatePolicyCoveragePayload,
  CreatePolicyDocumentRequirementPayload,
  CreatePolicyItemPayload,
  CreatePolicyPayload,
  EndorsementRecord,
  EndorsementStatus,
  EndorsementType,
  InsuranceProductRecord,
  InsurerRecord,
  PolicyCoverageRecord,
  PolicyDocumentRequirementRecord,
  PolicyDocumentRequirementStatus,
  PolicyItemRecord,
  PolicyItemType,
  PolicyRecord,
  PolicyStatus,
  ProductCoverageRecord,
  TransitionPolicyPayload,
  UpdatePolicyPayload,
} from "../../core/api/insurance-core.types";
import { SalesFlowService } from "../../core/api/sales-flow.service";
import { CustomerRecord } from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-policies-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./tenant-policies-page.component.html",
  styleUrl: "./tenant-policies-page.component.scss",
})
export class TenantPoliciesPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  // Master data.
  customers = signal<CustomerRecord[]>([]);
  insurers = signal<InsurerRecord[]>([]);
  products = signal<InsuranceProductRecord[]>([]);
  productCoverages = signal<ProductCoverageRecord[]>([]);

  // Listing.
  policies = signal<PolicyRecord[]>([]);
  search = signal("");
  statusFilter = signal<PolicyStatus | "">("");

  // Create form.
  insuredPartyId = signal<number | null>(null);
  insurerId = signal<number | null>(null);
  productId = signal<number | null>(null);
  policyNumber = signal("");
  brokerReference = signal("");
  startDate = signal("");
  endDate = signal("");
  issueDate = signal("");
  currency = signal("BRL");
  premiumTotal = signal("0.00");
  taxTotal = signal("0.00");
  commissionTotal = signal<string>("");
  notes = signal("");

  // Editing.
  editing = signal<PolicyRecord | null>(null);
  editPolicyNumber = signal("");
  editBrokerReference = signal("");
  editStartDate = signal("");
  editEndDate = signal("");
  editIssueDate = signal("");
  editCurrency = signal("BRL");
  editPremiumTotal = signal("0.00");
  editTaxTotal = signal("0.00");
  editCommissionTotal = signal<string>("");
  editNotes = signal("");

  // Transition.
  transitionStatus = signal<PolicyStatus>("UNDERWRITING");
  transitionReason = signal("");

  // Subresources.
  items = signal<PolicyItemRecord[]>([]);
  coverages = signal<PolicyCoverageRecord[]>([]);
  docRequirements = signal<PolicyDocumentRequirementRecord[]>([]);
  endorsements = signal<EndorsementRecord[]>([]);

  // Add item.
  itemType = signal<PolicyItemType>("AUTO");
  itemDescription = signal("");
  itemSumInsured = signal("0.00");
  itemAttributesJson = signal("{}");

  // Add coverage.
  coverageId = signal<number | null>(null);
  coverageLimit = signal("0.00");
  coverageDeductible = signal("0.00");
  coveragePremium = signal("0.00");
  coverageEnabled = signal(true);

  // Add doc requirement.
  docCode = signal("");
  docRequired = signal(true);
  docStatus = signal<PolicyDocumentRequirementStatus>("PENDING");
  docDocumentId = signal("");

  // Add endorsement.
  endorsementType = signal<EndorsementType>("COVERAGE_CHANGE");
  endorsementStatus = signal<EndorsementStatus>("DRAFT");
  endorsementNumber = signal("");
  endorsementEffectiveDate = signal("");
  endorsementPayloadJson = signal("{}");

  readonly selectedCustomer = computed(() => {
    const id = this.insuredPartyId();
    if (!id) {
      return null;
    }
    return this.customers().find((c) => c.id === id) ?? null;
  });

  constructor(
    private readonly insuranceCoreService: InsuranceCoreService,
    private readonly salesFlowService: SalesFlowService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.bootstrap();
  }

  toNumber(value: unknown): number | null {
    const parsed = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return parsed;
  }

  bootstrap(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    // Load customers + insurers in parallel via independent requests.
    let customersDone = false;
    let insurersDone = false;
    const finalizeIfReady = () => {
      if (customersDone && insurersDone) {
        this.loadPolicies();
        this.loading.set(false);
      }
    };

    this.salesFlowService.listCustomers().subscribe({
      next: (rows) => {
        this.customers.set(rows);
        customersDone = true;
        finalizeIfReady();
      },
      error: () => {
        this.error.set("Erro ao carregar clientes.");
        this.loading.set(false);
      },
    });

    this.insuranceCoreService.listInsurers({ status: "ACTIVE" }).subscribe({
      next: (rows) => {
        this.insurers.set(rows);
        insurersDone = true;
        finalizeIfReady();
      },
      error: () => {
        this.error.set("Erro ao carregar seguradoras.");
        this.loading.set(false);
      },
    });
  }

  loadPolicies(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService
      .listPolicies({ q: this.search(), status: this.statusFilter() })
      .subscribe({
        next: (rows) => {
          this.policies.set(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? typeof err.error.detail === "string"
                ? err.error.detail
                : JSON.stringify(err.error.detail)
              : "Erro ao carregar apólices."
          );
          this.loading.set(false);
        },
      });
  }

  onInsurerChange(insurerId: number | null): void {
    this.insurerId.set(insurerId);
    this.productId.set(null);
    this.products.set([]);
    this.productCoverages.set([]);

    if (!insurerId) {
      return;
    }

    this.insuranceCoreService.listProducts({ insurer_id: insurerId, status: "ACTIVE" }).subscribe({
      next: (rows) => this.products.set(rows),
      error: () => this.error.set("Erro ao carregar produtos da seguradora."),
    });
  }

  onProductChange(productId: number | null): void {
    this.productId.set(productId);
    this.productCoverages.set([]);
    this.coverageId.set(null);

    if (!productId) {
      return;
    }

    this.insuranceCoreService.listCoverages({ product_id: productId }).subscribe({
      next: (rows) => this.productCoverages.set(rows),
      error: () => this.error.set("Erro ao carregar coberturas do produto."),
    });
  }

  createPolicy(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const insuredPartyId = this.insuredPartyId();
    const insurerId = this.insurerId();
    const productId = this.productId();
    if (!insuredPartyId) {
      this.error.set("Selecione o cliente/segurado.");
      return;
    }
    if (!insurerId) {
      this.error.set("Selecione a seguradora.");
      return;
    }
    if (!productId) {
      this.error.set("Selecione o produto/ramo.");
      return;
    }
    if (!this.startDate().trim() || !this.endDate().trim()) {
      this.error.set("Preencha início e fim de vigência.");
      return;
    }

    const payload: CreatePolicyPayload = {
      insured_party_id: insuredPartyId,
      insurer_id: insurerId,
      product_id: productId,
      policy_number: this.policyNumber().trim() || null,
      broker_reference: this.brokerReference().trim(),
      start_date: this.startDate().trim(),
      end_date: this.endDate().trim(),
      issue_date: this.issueDate().trim() || null,
      currency: this.currency().trim() || "BRL",
      premium_total: this.premiumTotal().trim() || "0.00",
      tax_total: this.taxTotal().trim() || "0.00",
      commission_total: this.commissionTotal().trim() || null,
      notes: this.notes().trim(),
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createPolicy(payload).subscribe({
      next: (created) => {
        this.notice.set(`Apólice #${created.id} criada (status: ${created.status}).`);
        this.resetCreateForm();
        this.loadPolicies();
        this.startEdit(created);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao criar apólice."
        );
        this.loading.set(false);
      },
    });
  }

  resetCreateForm(): void {
    this.policyNumber.set("");
    this.brokerReference.set("");
    this.issueDate.set("");
    this.currency.set("BRL");
    this.premiumTotal.set("0.00");
    this.taxTotal.set("0.00");
    this.commissionTotal.set("");
    this.notes.set("");
  }

  startEdit(policy: PolicyRecord): void {
    this.editing.set(policy);
    this.editPolicyNumber.set(policy.policy_number ?? "");
    this.editBrokerReference.set(policy.broker_reference ?? "");
    this.editStartDate.set(policy.start_date ?? "");
    this.editEndDate.set(policy.end_date ?? "");
    this.editIssueDate.set(policy.issue_date ?? "");
    this.editCurrency.set(policy.currency ?? "BRL");
    this.editPremiumTotal.set(policy.premium_total ?? "0.00");
    this.editTaxTotal.set(policy.tax_total ?? "0.00");
    this.editCommissionTotal.set(policy.commission_total ?? "");
    this.editNotes.set(policy.notes ?? "");

    // Load product coverages for selected product so the coverage form works.
    const productId = policy.product?.id;
    if (productId) {
      this.onProductChange(productId);
    }

    this.loadSubresources(policy.id);
  }

  cancelEdit(): void {
    this.editing.set(null);
    this.items.set([]);
    this.coverages.set([]);
    this.docRequirements.set([]);
    this.endorsements.set([]);
  }

  deletePolicy(policy: PolicyRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const confirmed = window.confirm(
      "Excluir apólice? Somente apólices em DRAFT podem ser removidas."
    );
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deletePolicy(policy.id).subscribe({
      next: () => {
        this.notice.set("Apólice removida.");
        const editing = this.editing();
        if (editing && editing.id === policy.id) {
          this.cancelEdit();
        }
        this.loadPolicies();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao excluir apólice."
        );
        this.loading.set(false);
      },
    });
  }

  saveEdit(): void {
    const policy = this.editing();
    if (!policy) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const payload: UpdatePolicyPayload = {
      policy_number: this.editPolicyNumber().trim() || null,
      broker_reference: this.editBrokerReference().trim(),
      start_date: this.editStartDate().trim(),
      end_date: this.editEndDate().trim(),
      issue_date: this.editIssueDate().trim() || null,
      currency: this.editCurrency().trim() || "BRL",
      premium_total: this.editPremiumTotal().trim() || "0.00",
      tax_total: this.editTaxTotal().trim() || "0.00",
      commission_total: this.editCommissionTotal().trim() || null,
      notes: this.editNotes().trim(),
    };

    if (!payload.start_date || !payload.end_date) {
      this.error.set("Início e fim de vigência são obrigatórios.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.updatePolicy(policy.id, payload).subscribe({
      next: (updated) => {
        this.notice.set("Apólice atualizada.");
        this.loading.set(false);
        this.loadPolicies();
        this.editing.set(updated);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao atualizar apólice."
        );
        this.loading.set(false);
      },
    });
  }

  transition(): void {
    const policy = this.editing();
    if (!policy) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const payload: TransitionPolicyPayload = {
      status: this.transitionStatus(),
      reason: this.transitionReason().trim(),
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.transitionPolicy(policy.id, payload).subscribe({
      next: (updated) => {
        this.notice.set(`Status atualizado: ${policy.status} -> ${updated.status}`);
        this.transitionReason.set("");
        this.loading.set(false);
        this.loadPolicies();
        this.editing.set(updated);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao transicionar status."
        );
        this.loading.set(false);
      },
    });
  }

  loadSubresources(policyId: number): void {
    this.items.set([]);
    this.coverages.set([]);
    this.docRequirements.set([]);
    this.endorsements.set([]);

    this.insuranceCoreService.listPolicyItems(policyId).subscribe({
      next: (rows) => this.items.set(rows),
      error: () => this.error.set("Erro ao carregar itens da apólice."),
    });
    this.insuranceCoreService.listPolicyCoverages(policyId).subscribe({
      next: (rows) => this.coverages.set(rows),
      error: () => this.error.set("Erro ao carregar coberturas da apólice."),
    });
    this.insuranceCoreService.listPolicyDocumentRequirements(policyId).subscribe({
      next: (rows) => this.docRequirements.set(rows),
      error: () => this.error.set("Erro ao carregar documentos da apólice."),
    });
    this.insuranceCoreService.listEndorsements(policyId).subscribe({
      next: (rows) => this.endorsements.set(rows),
      error: () => this.error.set("Erro ao carregar endossos da apólice."),
    });
  }

  addItem(): void {
    const policy = this.editing();
    if (!policy) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    let attributes: Record<string, unknown> = {};
    const rawJson = this.itemAttributesJson().trim();
    if (rawJson) {
      try {
        const parsed = JSON.parse(rawJson);
        attributes = typeof parsed === "object" && parsed ? parsed : {};
      } catch {
        this.error.set("Atributos do item devem ser um JSON válido.");
        return;
      }
    }

    const payload: CreatePolicyItemPayload = {
      policy_id: policy.id,
      item_type: this.itemType(),
      description: this.itemDescription().trim(),
      sum_insured: this.itemSumInsured().trim() || "0.00",
      attributes,
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createPolicyItem(payload).subscribe({
      next: () => {
        this.notice.set("Item adicionado.");
        this.itemDescription.set("");
        this.itemSumInsured.set("0.00");
        this.itemAttributesJson.set("{}");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao adicionar item.");
        this.loading.set(false);
      },
    });
  }

  deleteItem(item: PolicyItemRecord): void {
    const policy = this.editing();
    if (!policy || !this.canWrite()) {
      return;
    }
    const confirmed = window.confirm("Remover este item?");
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deletePolicyItem(item.id).subscribe({
      next: () => {
        this.notice.set("Item removido.");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: () => {
        this.error.set("Erro ao remover item.");
        this.loading.set(false);
      },
    });
  }

  addCoverage(): void {
    const policy = this.editing();
    const coverageId = this.coverageId();
    if (!policy || !coverageId) {
      this.error.set("Selecione uma cobertura.");
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const payload: CreatePolicyCoveragePayload = {
      policy_id: policy.id,
      product_coverage_id: coverageId,
      limit_amount: this.coverageLimit().trim() || "0.00",
      deductible_amount: this.coverageDeductible().trim() || "0.00",
      premium_amount: this.coveragePremium().trim() || "0.00",
      is_enabled: this.coverageEnabled(),
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createPolicyCoverage(payload).subscribe({
      next: () => {
        this.notice.set("Cobertura adicionada.");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao adicionar cobertura.");
        this.loading.set(false);
      },
    });
  }

  deleteCoverage(coverage: PolicyCoverageRecord): void {
    const policy = this.editing();
    if (!policy || !this.canWrite()) {
      return;
    }
    const confirmed = window.confirm("Remover esta cobertura?");
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deletePolicyCoverage(coverage.id).subscribe({
      next: () => {
        this.notice.set("Cobertura removida.");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: () => {
        this.error.set("Erro ao remover cobertura.");
        this.loading.set(false);
      },
    });
  }

  addDocRequirement(): void {
    const policy = this.editing();
    if (!policy) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const code = this.docCode().trim();
    if (!code) {
      this.error.set("Código do documento é obrigatório.");
      return;
    }

    const payload: CreatePolicyDocumentRequirementPayload = {
      policy_id: policy.id,
      requirement_code: code,
      required: this.docRequired(),
      status: this.docStatus(),
      document_id: this.docDocumentId().trim(),
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createPolicyDocumentRequirement(payload).subscribe({
      next: () => {
        this.notice.set("Documento adicionado.");
        this.docCode.set("");
        this.docDocumentId.set("");
        this.docStatus.set("PENDING");
        this.docRequired.set(true);
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao adicionar documento.");
        this.loading.set(false);
      },
    });
  }

  deleteDocRequirement(doc: PolicyDocumentRequirementRecord): void {
    const policy = this.editing();
    if (!policy || !this.canWrite()) {
      return;
    }
    const confirmed = window.confirm("Remover este documento?");
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deletePolicyDocumentRequirement(doc.id).subscribe({
      next: () => {
        this.notice.set("Documento removido.");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: () => {
        this.error.set("Erro ao remover documento.");
        this.loading.set(false);
      },
    });
  }

  addEndorsement(): void {
    const policy = this.editing();
    if (!policy) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const effectiveDate = this.endorsementEffectiveDate().trim();
    if (!effectiveDate) {
      this.error.set("Data de vigência do endosso é obrigatória.");
      return;
    }

    let payloadObj: Record<string, unknown> = {};
    const raw = this.endorsementPayloadJson().trim();
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        payloadObj = typeof parsed === "object" && parsed ? parsed : {};
      } catch {
        this.error.set("Payload do endosso deve ser um JSON válido.");
        return;
      }
    }

    const payload: CreateEndorsementPayload = {
      policy_id: policy.id,
      endorsement_number: this.endorsementNumber().trim() || null,
      type: this.endorsementType(),
      status: this.endorsementStatus(),
      effective_date: effectiveDate,
      payload: payloadObj,
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createEndorsement(payload).subscribe({
      next: () => {
        this.notice.set("Endosso criado.");
        this.endorsementNumber.set("");
        this.endorsementStatus.set("DRAFT");
        this.endorsementType.set("COVERAGE_CHANGE");
        this.endorsementEffectiveDate.set("");
        this.endorsementPayloadJson.set("{}");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao criar endosso.");
        this.loading.set(false);
      },
    });
  }

  deleteEndorsement(endorsement: EndorsementRecord): void {
    const policy = this.editing();
    if (!policy || !this.canWrite()) {
      return;
    }
    const confirmed = window.confirm("Remover este endosso?");
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deleteEndorsement(endorsement.id).subscribe({
      next: () => {
        this.notice.set("Endosso removido.");
        this.loading.set(false);
        this.loadSubresources(policy.id);
      },
      error: () => {
        this.error.set("Erro ao remover endosso.");
        this.loading.set(false);
      },
    });
  }
}
