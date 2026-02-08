import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { Router } from "@angular/router";
import { forkJoin } from "rxjs";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  LeadRecord,
  OpportunityRecord,
  OpportunityStage,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-sales-flow-page",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./sales-flow-page.component.html",
  styleUrl: "./sales-flow-page.component.scss",
})
export class SalesFlowPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  leads = signal<LeadRecord[]>([]);
  opportunities = signal<OpportunityRecord[]>([]);

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

    forkJoin({
      leads: this.salesFlowService.listLeads(),
      opportunities: this.salesFlowService.listOpportunities(),
    }).subscribe({
      next: (result) => {
        this.leads.set(result.leads);
        this.opportunities.set(result.opportunities);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar fluxo comercial."
        );
        this.loading.set(false);
      },
    });
  }

  qualifyLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.salesFlowService.qualifyLead(lead.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao qualificar lead."),
    });
  }

  disqualifyLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.salesFlowService.disqualifyLead(lead.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao desqualificar lead."),
    });
  }

  convertLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.salesFlowService.convertLead(lead.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao converter lead."),
    });
  }

  moveToNextStage(opportunity: OpportunityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const next = this.getNextStage(opportunity.stage);
    if (!next) {
      this.error.set("Oportunidade já está em estágio final.");
      return;
    }
    this.loading.set(true);
    this.salesFlowService.updateOpportunityStage(opportunity.id, next).subscribe({
      next: () => this.load(),
      error: (err) =>
        this.handleActionError(err, "Erro ao avançar estágio da oportunidade."),
    });
  }

  markLost(opportunity: OpportunityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (opportunity.stage === "LOST") {
      return;
    }
    this.loading.set(true);
    this.salesFlowService.updateOpportunityStage(opportunity.id, "LOST").subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao marcar oportunidade como perdida."),
    });
  }

  private getNextStage(stage: OpportunityStage): OpportunityStage | null {
    if (stage === "DISCOVERY") {
      return "PROPOSAL";
    }
    if (stage === "PROPOSAL") {
      return "NEGOTIATION";
    }
    if (stage === "NEGOTIATION") {
      return "WON";
    }
    return null;
  }

  private handleActionError(err: unknown, fallbackMessage: string): void {
    const maybeError = err as { error?: { detail?: unknown } };
    this.error.set(
      maybeError?.error?.detail
        ? JSON.stringify(maybeError.error.detail)
        : fallbackMessage
    );
    this.loading.set(false);
  }
}
