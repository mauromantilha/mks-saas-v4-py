import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  AIInsightResponse,
  CreateOpportunityPayload,
  CustomerRecord,
  OpportunityRecord,
  OpportunityStage,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

type OpportunityViewMode = "KANBAN" | "LIST";

interface StageColumn {
  stage: OpportunityStage;
  label: string;
  help: string;
}

const PIPELINE_COLUMNS: StageColumn[] = [
  { stage: "NEW", label: "Novo / Sem contato", help: "Entrada no pipeline. SLA de abordagem." },
  { stage: "QUALIFICATION", label: "Qualificação", help: "Validação de fit e decisor." },
  { stage: "NEEDS_ASSESSMENT", label: "Necessidades", help: "Levantamento detalhado (formulário dinâmico)." },
  { stage: "QUOTATION", label: "Cotação", help: "Envio a multicálculo/seguradoras e consolidação." },
  { stage: "PROPOSAL_PRESENTATION", label: "Proposta", help: "Apresentação comparativa com tracking." },
  { stage: "NEGOTIATION", label: "Negociação", help: "Ajustes finais de cobertura e preço." },
  { stage: "WON", label: "Ganha", help: "Venda fechada (handover: pedido de emissão automático)." },
  { stage: "LOST", label: "Perdida", help: "Motivo de perda e lições aprendidas." },
];

@Component({
  selector: "app-tenant-opportunities-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./tenant-opportunities-page.component.html",
  styleUrl: "./tenant-opportunities-page.component.scss",
})
export class TenantOpportunitiesPageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  mode = signal<OpportunityViewMode>("KANBAN");
  customers = signal<CustomerRecord[]>([]);
  opportunities = signal<OpportunityRecord[]>([]);

  draggedOpportunityId = signal<number | null>(null);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  // Create form.
  customerId = signal("");
  title = signal("");
  amount = signal("");
  stage = signal<OpportunityStage>("NEW");

  readonly columns = PIPELINE_COLUMNS;

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

  setMode(mode: OpportunityViewMode): void {
    this.mode.set(mode);
    this.error.set("");
    this.notice.set("");
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.listCustomers().subscribe({
      next: (customers) => {
        this.customers.set(customers);
        this.salesFlowService.listOpportunities().subscribe({
          next: (opportunities) => {
            this.opportunities.set(opportunities);
            this.loading.set(false);
          },
          error: (err) => this.handleLoadError(err, "Erro ao carregar oportunidades."),
        });
      },
      error: (err) => this.handleLoadError(err, "Erro ao carregar clientes."),
    });
  }

  opportunitiesForStage(stage: OpportunityStage): OpportunityRecord[] {
    return this.opportunities().filter((opp) => opp.stage === stage);
  }

  createOpportunity(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const customerId = Number.parseInt(this.customerId(), 10);
    if (Number.isNaN(customerId)) {
      this.error.set("Selecione o cliente da oportunidade.");
      return;
    }
    const title = this.title().trim();
    if (!title) {
      this.error.set("Título é obrigatório.");
      return;
    }
    const payload: CreateOpportunityPayload = {
      customer: customerId,
      title,
      stage: this.stage(),
      amount: this.amount().trim() || undefined,
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.createOpportunity(payload).subscribe({
      next: (opp) => {
        this.notice.set(`Oportunidade #${opp.id} criada.`);
        this.resetForm();
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao criar oportunidade."
        );
        this.loading.set(false);
      },
    });
  }

  resetForm(): void {
    this.customerId.set("");
    this.title.set("");
    this.amount.set("");
    this.stage.set("NEW");
  }

  formatCurrency(value: string | number | null | undefined): string {
    const numeric = typeof value === "string" ? Number.parseFloat(value) : Number(value ?? 0);
    return this.brlFormatter.format(Number.isFinite(numeric) ? numeric : 0);
  }

  onDragStart(event: DragEvent, opportunity: OpportunityRecord): void {
    this.draggedOpportunityId.set(opportunity.id);
    try {
      event.dataTransfer?.setData("text/plain", String(opportunity.id));
      event.dataTransfer?.setDragImage(new Image(), 0, 0);
    } catch {
      // Ignore.
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "move";
    }
  }

  onDrop(event: DragEvent, targetStage: OpportunityStage): void {
    event.preventDefault();
    const raw = event.dataTransfer?.getData("text/plain") || "";
    const id = Number.parseInt(raw || String(this.draggedOpportunityId() ?? ""), 10);
    if (!Number.isInteger(id)) {
      return;
    }

    const opp = this.opportunities().find((item) => item.id === id);
    if (!opp) {
      return;
    }
    if (opp.stage === targetStage) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.updateOpportunityStage(opp.id, targetStage).subscribe({
      next: () => {
        this.notice.set(`Oportunidade #${opp.id} movida para ${targetStage}.`);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao mover oportunidade."
        );
        this.loading.set(false);
      },
    });
  }

  generateInsights(opp: OpportunityRecord): void {
    this.aiEntityLabel.set(`Oportunidade #${opp.id}`);
    this.aiResponse.set(null);
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .generateOpportunityAIInsights(opp.id, { include_cnpj_enrichment: true })
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

  private handleLoadError(err: any, fallback: string): void {
    this.error.set(err?.error?.detail ? JSON.stringify(err.error.detail) : fallback);
    this.loading.set(false);
  }
}

