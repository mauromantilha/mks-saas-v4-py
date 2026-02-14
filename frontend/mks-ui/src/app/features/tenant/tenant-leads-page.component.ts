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
import { normalizeListResponse } from "../../shared/api/response-normalizers";

type LeadViewMode = "KANBAN" | "LIST";
type LeadKanbanStage = "PROSPECCAO" | "QUALIFICACAO" | "COTACAO" | "PROPOSTA";
type LeadKanbanColumnKey = LeadKanbanStage | "FINAL";

interface LeadColumn {
  key: LeadKanbanColumnKey;
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
  leadAction = signal<LeadKanbanStage>("PROSPECCAO");
  leadFullName = signal("");
  leadCompanyName = signal("");
  leadEmail = signal("");
  leadPhone = signal("");
  leadCnpj = signal("");
  leadProductsOfInterest = signal("");
  leadEstimatedBudget = signal("");
  leadNotes = signal("");

  readonly leadSourceOptions = [
    { label: "Indicação", value: "INDICACAO" },
    { label: "Site", value: "SITE" },
    { label: "LinkedIn", value: "LINKEDIN" },
    { label: "Instagram", value: "INSTAGRAM" },
    { label: "Facebook", value: "FACEBOOK" },
    { label: "WhatsApp", value: "WHATSAPP" },
    { label: "Outro", value: "OUTRO" },
  ];

  readonly actionOptions: Array<{ label: string; value: LeadKanbanStage }> = [
    { label: "Prospecção", value: "PROSPECCAO" },
    { label: "Qualificação", value: "QUALIFICACAO" },
    { label: "Cotação", value: "COTACAO" },
    { label: "Proposta", value: "PROPOSTA" },
  ];

  readonly columns: LeadColumn[] = [
    {
      key: "PROSPECCAO",
      label: "Prospecção",
      help: "Leads novos sem qualificação concluída.",
    },
    {
      key: "QUALIFICACAO",
      label: "Qualificação",
      help: "Contato feito e necessidades iniciais levantadas.",
    },
    {
      key: "COTACAO",
      label: "Cotação",
      help: "Leads com fase de cotação comercial.",
    },
    {
      key: "PROPOSTA",
      label: "Proposta",
      help: "Leads em apresentação ou ajuste de proposta.",
    },
    {
      key: "FINAL",
      label: "Convertido ou Perdido",
      help: "Final do funil: convertido em cliente ou perdido.",
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
      next: (response) => {
        const normalized = normalizeListResponse<LeadRecord>(response);
        this.leads.set(normalized.results);
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

  leadsForColumn(column: LeadKanbanColumnKey): LeadRecord[] {
    return this.leads().filter((lead) => this.resolveColumn(lead) === column);
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
    const action = this.leadAction();

    const estimatedBudget = this.leadEstimatedBudget().trim();
    const stageAwareNotes = this.withStageTag(this.leadNotes().trim(), action);
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
        notes: stageAwareNotes,
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
    this.leadAction.set("PROSPECCAO");
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

  onDrop(event: DragEvent, targetColumn: LeadKanbanColumnKey): void {
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
    const currentColumn = this.resolveColumn(lead);
    if (currentColumn === targetColumn) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    if (targetColumn === "PROSPECCAO") {
      this.loading.set(false);
      this.error.set("Não é permitido mover o lead de volta para Prospecção.");
      return;
    }

    if (targetColumn === "QUALIFICACAO" || targetColumn === "COTACAO" || targetColumn === "PROPOSTA") {
      const patchedNotes = this.withStageTag(this.stripStageTag(lead.notes || ""), targetColumn);

      if (lead.status === "NEW") {
        this.salesFlowService.qualifyLead(lead.id).subscribe({
          next: () => {
            this.salesFlowService.updateLead(lead.id, { notes: patchedNotes }).subscribe({
              next: () => {
                this.notice.set(`Lead #${lead.id} movido para ${this.labelForStage(targetColumn)}.`);
                this.load();
              },
              error: (err) => this.handleMoveError(err),
            });
          },
          error: (err) => this.handleMoveError(err),
        });
        return;
      }

      if (lead.status === "QUALIFIED") {
        this.salesFlowService.updateLead(lead.id, { notes: patchedNotes }).subscribe({
          next: () => {
            this.notice.set(`Lead #${lead.id} movido para ${this.labelForStage(targetColumn)}.`);
            this.load();
          },
          error: (err) => this.handleMoveError(err),
        });
        return;
      }

      this.loading.set(false);
      this.error.set("Lead finalizado não pode voltar para etapas de funil.");
      return;
    }

    if (targetColumn === "FINAL") {
      if (lead.status === "NEW") {
        this.salesFlowService.disqualifyLead(lead.id).subscribe({
          next: () => {
            this.notice.set(`Lead #${lead.id} marcado como perdido.`);
            this.load();
          },
          error: (err) => this.handleMoveError(err),
        });
        return;
      }

      if (lead.status === "QUALIFIED") {
        this.salesFlowService
          .convertLead(lead.id, { create_customer_if_missing: true })
          .subscribe({
            next: (payload) => {
              this.notice.set(
                `Lead #${lead.id} convertido: cliente #${payload.customer.id} criado com dados pré-preenchidos para completar manualmente.`
              );
              this.load();
            },
            error: (err) => this.handleMoveError(err),
          });
        return;
      }

      this.loading.set(false);
      return;
    }
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

  private resolveColumn(lead: LeadRecord): LeadKanbanColumnKey {
    if (lead.status === "CONVERTED" || lead.status === "DISQUALIFIED") {
      return "FINAL";
    }

    if (lead.status === "NEW") {
      return "PROSPECCAO";
    }

    const stage = this.readStageTag(lead.notes || "");
    if (stage === "COTACAO") {
      return "COTACAO";
    }
    if (stage === "PROPOSTA") {
      return "PROPOSTA";
    }
    return "QUALIFICACAO";
  }

  private readStageTag(notes: string): LeadKanbanStage | null {
    const match = String(notes || "").match(/^\[STAGE:(PROSPECCAO|QUALIFICACAO|COTACAO|PROPOSTA)\]/i);
    if (!match) {
      return null;
    }
    return String(match[1]).toUpperCase() as LeadKanbanStage;
  }

  private stripStageTag(notes: string): string {
    return String(notes || "")
      .replace(/^\[STAGE:(PROSPECCAO|QUALIFICACAO|COTACAO|PROPOSTA)\]\s*/i, "")
      .trim();
  }

  private withStageTag(notes: string, stage: LeadKanbanStage): string {
    const cleanNotes = this.stripStageTag(notes);
    const prefix = `[STAGE:${stage}]`;
    return cleanNotes ? `${prefix} ${cleanNotes}` : prefix;
  }

  private labelForStage(stage: LeadKanbanStage): string {
    if (stage === "PROSPECCAO") {
      return "Prospecção";
    }
    if (stage === "QUALIFICACAO") {
      return "Qualificação";
    }
    if (stage === "COTACAO") {
      return "Cotação";
    }
    return "Proposta";
  }
}
