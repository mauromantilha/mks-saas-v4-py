import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  CustomerRecord,
  LeadRecord,
  OpportunityRecord,
  PolicyRequestRecord,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-policy-requests-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-policy-requests-page.component.html",
  styleUrl: "./tenant-policy-requests-page.component.scss",
})
export class TenantPolicyRequestsPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");
  aiResult = signal("");

  opportunities = signal<OpportunityRecord[]>([]);
  customers = signal<CustomerRecord[]>([]);
  leads = signal<LeadRecord[]>([]);
  requests = signal<PolicyRequestRecord[]>([]);

  opportunity = signal<number | null>(null);
  customer = signal<number | null>(null);
  sourceLead = signal<number | null>(null);
  productLine = signal("");
  inspectionRequired = signal(true);
  issueDeadlineAt = signal("");
  notes = signal("");
  statusFilter = signal<
    "PENDING_DATA" | "UNDER_REVIEW" | "READY_TO_ISSUE" | "ISSUED" | "REJECTED" | ""
  >("");

  editing = signal<PolicyRequestRecord | null>(null);
  editStatus = signal<PolicyRequestRecord["status"]>("PENDING_DATA");
  editInspectionRequired = signal(false);
  editInspectionStatus = signal<PolicyRequestRecord["inspection_status"]>("NOT_REQUIRED");
  editInspectionScheduledAt = signal("");
  editBillingMethod = signal<PolicyRequestRecord["billing_method"]>("");
  editPaymentDay = signal<number | null>(null);
  editFinalPremium = signal("");
  editFinalCommission = signal("");
  editIssueDeadlineAt = signal("");
  editNotes = signal("");

  constructor(
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

  private parseError(err: unknown, fallback: string): string {
    const candidate = err as { error?: { detail?: unknown } };
    const detail = candidate?.error?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (detail) {
      return JSON.stringify(detail);
    }
    return fallback;
  }

  private toIsoDate(value: string | null): string {
    if (!value) {
      return "";
    }
    return value.slice(0, 10);
  }

  private toIsoDateTime(value: string): string | null {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    if (trimmed.includes("T")) {
      return trimmed;
    }
    return `${trimmed}T00:00:00Z`;
  }

  bootstrap(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");
    let done = 0;
    const markDone = () => {
      done += 1;
      if (done >= 4) {
        this.loading.set(false);
      }
    };

    this.salesFlowService.listOpportunities().subscribe({
      next: (rows) => {
        this.opportunities.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar oportunidades.");
        this.loading.set(false);
      },
    });

    this.salesFlowService.listCustomers().subscribe({
      next: (rows) => {
        this.customers.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar clientes.");
        this.loading.set(false);
      },
    });

    this.salesFlowService.listLeads().subscribe({
      next: (rows) => {
        this.leads.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar leads.");
        this.loading.set(false);
      },
    });

    this.salesFlowService.listPolicyRequests().subscribe({
      next: (rows) => {
        this.requests.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar pedidos de emissão.");
        this.loading.set(false);
      },
    });
  }

  filteredRequests(): PolicyRequestRecord[] {
    if (!this.statusFilter()) {
      return this.requests();
    }
    return this.requests().filter((row) => row.status === this.statusFilter());
  }

  onOpportunityChange(value: string): void {
    const id = Number(value);
    this.opportunity.set(Number.isFinite(id) && id > 0 ? id : null);
    const selected = this.opportunities().find((row) => row.id === id);
    this.customer.set(selected ? selected.customer : this.customer());
    if (selected?.source_lead) {
      this.sourceLead.set(selected.source_lead);
    }
    if (selected?.product_line) {
      this.productLine.set(selected.product_line);
    }
  }

  createRequest(): void {
    if (!this.canWrite()) {
      return;
    }
    if (!this.opportunity()) {
      this.error.set("Selecione uma oportunidade.");
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");

    this.salesFlowService
      .createPolicyRequest({
        opportunity: this.opportunity() as number,
        customer: this.customer() || undefined,
        source_lead: this.sourceLead(),
        product_line: this.productLine().trim() || undefined,
        inspection_required: this.inspectionRequired(),
        issue_deadline_at: this.toIsoDateTime(this.issueDeadlineAt()),
        notes: this.notes().trim() || undefined,
      })
      .subscribe({
        next: () => {
          this.notice.set("Pedido de emissão criado.");
          this.productLine.set("");
          this.notes.set("");
          this.issueDeadlineAt.set("");
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao criar pedido de emissão."));
          this.loading.set(false);
        },
      });
  }

  startEdit(record: PolicyRequestRecord): void {
    this.editing.set(record);
    this.editStatus.set(record.status);
    this.editInspectionRequired.set(record.inspection_required);
    this.editInspectionStatus.set(record.inspection_status);
    this.editInspectionScheduledAt.set(this.toIsoDate(record.inspection_scheduled_at));
    this.editBillingMethod.set(record.billing_method);
    this.editPaymentDay.set(record.payment_day);
    this.editFinalPremium.set(record.final_premium ?? "");
    this.editFinalCommission.set(record.final_commission ?? "");
    this.editIssueDeadlineAt.set(this.toIsoDate(record.issue_deadline_at));
    this.editNotes.set(record.notes ?? "");
    this.aiResult.set("");
  }

  cancelEdit(): void {
    this.editing.set(null);
    this.aiResult.set("");
  }

  saveEdit(): void {
    const record = this.editing();
    if (!record || !this.canWrite()) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .updatePolicyRequest(record.id, {
        status: this.editStatus(),
        inspection_required: this.editInspectionRequired(),
        inspection_status: this.editInspectionStatus(),
        inspection_scheduled_at: this.toIsoDateTime(this.editInspectionScheduledAt()),
        billing_method: this.editBillingMethod(),
        payment_day: this.editPaymentDay(),
        final_premium: this.editFinalPremium() || null,
        final_commission: this.editFinalCommission() || null,
        issue_deadline_at: this.toIsoDateTime(this.editIssueDeadlineAt()),
        notes: this.editNotes().trim() || "",
      })
      .subscribe({
        next: () => {
          this.notice.set("Pedido de emissão atualizado.");
          this.cancelEdit();
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao atualizar pedido de emissão."));
          this.loading.set(false);
        },
      });
  }

  runAiInsights(): void {
    const record = this.editing();
    if (!record) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");
    this.salesFlowService
      .generatePolicyRequestAIInsights(record.id, {
        focus: "handover",
        include_cnpj_enrichment: true,
      })
      .subscribe({
        next: (resp) => {
          this.aiResult.set(JSON.stringify(resp.insights, null, 2));
          this.notice.set("Insights de IA atualizados.");
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao gerar insights de IA."));
          this.loading.set(false);
        },
      });
  }

  customerLabel(id: number | null): string {
    if (!id) {
      return "-";
    }
    return this.customers().find((row) => row.id === id)?.name ?? `#${id}`;
  }

  leadLabel(id: number | null): string {
    if (!id) {
      return "-";
    }
    const lead = this.leads().find((row) => row.id === id);
    return lead ? `${lead.full_name || lead.company_name || "Lead"} (#${id})` : `#${id}`;
  }
}
