import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  AIInsightResponse,
  LeadRecord,
  LeadStatus,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

type LeadViewMode = "KANBAN" | "LIST";

interface LeadColumn {
  status: LeadStatus;
  label: string;
  help: string;
}

@Component({
  selector: "app-tenant-leads-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-leads-page.component.html",
  styleUrl: "./tenant-leads-page.component.scss",
})
export class TenantLeadsPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  mode = signal<LeadViewMode>("KANBAN");
  leads = signal<LeadRecord[]>([]);

  draggedLeadId = signal<number | null>(null);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  // Lead create form.
  leadSource = signal("");
  leadFullName = signal("");
  leadCompanyName = signal("");
  leadEmail = signal("");
  leadPhone = signal("");
  leadCnpj = signal("");
  leadProductsOfInterest = signal("");
  leadEstimatedBudget = signal("");
  leadNotes = signal("");

  readonly columns: LeadColumn[] = [
    {
      status: "NEW",
      label: "Novo / Sem contato",
      help: "Lead recém-chegado. SLA de primeiro contato roda aqui.",
    },
    {
      status: "QUALIFIED",
      label: "Qualificação",
      help: "Contato feito, necessidades iniciais mapeadas.",
    },
    {
      status: "DISQUALIFIED",
      label: "Desqualificado",
      help: "Sem fit, sem interesse ou dados insuficientes.",
    },
    {
      status: "CONVERTED",
      label: "Convertido",
      help: "Virou cliente + oportunidade + pedido de emissão.",
    },
  ];

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

  setMode(mode: LeadViewMode): void {
    this.mode.set(mode);
    this.error.set("");
    this.notice.set("");
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.listLeads().subscribe({
      next: (leads) => {
        this.leads.set(leads);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao carregar leads."
        );
        this.loading.set(false);
      },
    });
  }

  leadsForStatus(status: LeadStatus): LeadRecord[] {
    return this.leads().filter((lead) => lead.status === status);
  }

  createLead(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const source = this.leadSource().trim();
    if (!source) {
      this.error.set("Origem do lead é obrigatória.");
      return;
    }

    const estimatedBudget = this.leadEstimatedBudget().trim();
    this.loading.set(true);
    this.notice.set("");
    this.error.set("");

    this.salesFlowService
      .createLead({
        source,
        full_name: this.leadFullName().trim(),
        company_name: this.leadCompanyName().trim(),
        email: this.leadEmail().trim(),
        phone: this.leadPhone().trim(),
        cnpj: this.leadCnpj().trim(),
        products_of_interest: this.leadProductsOfInterest().trim(),
        estimated_budget: estimatedBudget || undefined,
        notes: this.leadNotes().trim(),
        capture_channel: "MANUAL",
      })
      .subscribe({
        next: (lead) => {
          this.notice.set(`Lead #${lead.id} criado (IA + score aplicados automaticamente).`);
          this.resetLeadForm();
          this.load();
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao criar lead."
          );
          this.loading.set(false);
        },
      });
  }

  resetLeadForm(): void {
    this.leadSource.set("");
    this.leadFullName.set("");
    this.leadCompanyName.set("");
    this.leadEmail.set("");
    this.leadPhone.set("");
    this.leadCnpj.set("");
    this.leadProductsOfInterest.set("");
    this.leadEstimatedBudget.set("");
    this.leadNotes.set("");
  }

  onDragStart(event: DragEvent, lead: LeadRecord): void {
    this.draggedLeadId.set(lead.id);
    try {
      event.dataTransfer?.setData("text/plain", String(lead.id));
      event.dataTransfer?.setDragImage(new Image(), 0, 0);
    } catch {
      // Some browsers restrict dataTransfer in certain contexts.
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "move";
    }
  }

  onDrop(event: DragEvent, targetStatus: LeadStatus): void {
    event.preventDefault();
    const raw = event.dataTransfer?.getData("text/plain") || "";
    const id = Number.parseInt(raw || String(this.draggedLeadId() ?? ""), 10);
    if (!Number.isInteger(id)) {
      return;
    }

    const lead = this.leads().find((item) => item.id === id);
    if (!lead) {
      return;
    }
    if (lead.status === targetStatus) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    if (targetStatus === "QUALIFIED") {
      this.salesFlowService.qualifyLead(lead.id).subscribe({
        next: () => {
          this.notice.set(`Lead #${lead.id} qualificado.`);
          this.load();
        },
        error: (err) => this.handleMoveError(err),
      });
      return;
    }

    if (targetStatus === "DISQUALIFIED") {
      this.salesFlowService.disqualifyLead(lead.id).subscribe({
        next: () => {
          this.notice.set(`Lead #${lead.id} desqualificado.`);
          this.load();
        },
        error: (err) => this.handleMoveError(err),
      });
      return;
    }

    if (targetStatus === "CONVERTED") {
      this.salesFlowService.convertLead(lead.id, { create_customer_if_missing: true }).subscribe({
        next: (payload) => {
          this.notice.set(
            `Lead #${lead.id} convertido: cliente #${payload.customer.id}, oportunidade #${payload.opportunity.id}.`
          );
          this.load();
        },
        error: (err) => this.handleMoveError(err),
      });
      return;
    }

    // NEW: revert is not supported by business rules.
    this.loading.set(false);
    this.error.set("Não é permitido mover o lead de volta para 'Novo'.");
  }

  generateInsights(lead: LeadRecord): void {
    this.aiEntityLabel.set(`Lead #${lead.id}`);
    this.aiResponse.set(null);
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.generateLeadAIInsights(lead.id, { include_cnpj_enrichment: true }).subscribe({
      next: (resp) => {
        this.aiResponse.set(resp);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao gerar insights IA."
        );
        this.loading.set(false);
      },
    });
  }

  enrichCnpj(lead: LeadRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.enrichLeadCnpj(lead.id).subscribe({
      next: () => {
        this.notice.set(`CNPJ enriquecido para Lead #${lead.id}.`);
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

  private handleMoveError(err: any): void {
    this.error.set(
      err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao mover lead."
    );
    this.loading.set(false);
  }
}

