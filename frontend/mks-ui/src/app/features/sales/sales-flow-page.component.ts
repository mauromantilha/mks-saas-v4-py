import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { forkJoin } from "rxjs";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  ActivityKind,
  ActivityPriority,
  CommercialActivityRecord,
  LeadRecord,
  LeadHistoryRecord,
  OpportunityRecord,
  OpportunityHistoryRecord,
  OpportunityStage,
  SalesMetricsRecord,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-sales-flow-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
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
  activities = signal<CommercialActivityRecord[]>([]);
  reminderActivities = signal<CommercialActivityRecord[]>([]);
  metrics = signal<SalesMetricsRecord | null>(null);
  leadHistory = signal<LeadHistoryRecord | null>(null);
  opportunityHistory = signal<OpportunityHistoryRecord | null>(null);

  activityKind = signal<ActivityKind>("FOLLOW_UP");
  activityPriority = signal<ActivityPriority>("MEDIUM");
  activityTitle = signal("");
  activityDescription = signal("");
  activityDueAt = signal("");
  activityReminderAt = signal("");
  activitySlaHours = signal("");
  activityTargetType = signal<"LEAD" | "OPPORTUNITY">("LEAD");
  activityTargetId = signal("");

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
      activities: this.salesFlowService.listActivities(),
      reminders: this.salesFlowService.listReminderActivities(),
      metrics: this.salesFlowService.getSalesMetrics(),
    }).subscribe({
      next: (result) => {
        this.leads.set(result.leads);
        this.opportunities.set(result.opportunities);
        this.activities.set(result.activities);
        this.reminderActivities.set(result.reminders);
        this.metrics.set(result.metrics);
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

  createActivity(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const title = this.activityTitle().trim();
    if (!title) {
      this.error.set("Título da atividade é obrigatório.");
      return;
    }

    const targetId = Number.parseInt(this.activityTargetId(), 10);
    if (Number.isNaN(targetId)) {
      this.error.set("Selecione o lead ou oportunidade para vincular a atividade.");
      return;
    }

    const dueAt = this.parseLocalDateTime(this.activityDueAt());
    const reminderAt = this.parseLocalDateTime(this.activityReminderAt());
    if (this.activityReminderAt().trim() && reminderAt === null) {
      this.error.set("Data de lembrete inválida.");
      return;
    }
    if (this.activityDueAt().trim() && dueAt === null) {
      this.error.set("Data de vencimento inválida.");
      return;
    }

    const slaHoursText = this.activitySlaHours().trim();
    let slaHours: number | null = null;
    if (slaHoursText) {
      slaHours = Number.parseInt(slaHoursText, 10);
      if (!Number.isInteger(slaHours) || slaHours <= 0) {
        this.error.set("SLA deve ser um número inteiro maior que zero.");
        return;
      }
    }

    const payload = {
      kind: this.activityKind(),
      title,
      description: this.activityDescription().trim(),
      priority: this.activityPriority(),
      due_at: dueAt,
      reminder_at: reminderAt,
      sla_hours: slaHours,
      lead: this.activityTargetType() === "LEAD" ? targetId : null,
      opportunity: this.activityTargetType() === "OPPORTUNITY" ? targetId : null,
    };

    this.loading.set(true);
    this.salesFlowService.createActivity(payload).subscribe({
      next: () => {
        this.resetActivityForm();
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao criar atividade."),
    });
  }

  completeActivity(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.status === "DONE") {
      return;
    }
    this.loading.set(true);
    this.salesFlowService.completeActivity(activity.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao concluir atividade."),
    });
  }

  reopenActivity(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.status !== "DONE") {
      return;
    }
    this.loading.set(true);
    this.salesFlowService.reopenActivity(activity.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao reabrir atividade."),
    });
  }

  markReminderSent(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.reminder_sent) {
      return;
    }
    this.loading.set(true);
    this.salesFlowService.markActivityReminded(activity.id).subscribe({
      next: () => this.load(),
      error: (err) => this.handleActionError(err, "Erro ao marcar lembrete enviado."),
    });
  }

  viewLeadHistory(lead: LeadRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.getLeadHistory(lead.id).subscribe({
      next: (payload) => {
        this.leadHistory.set(payload);
        this.opportunityHistory.set(null);
        this.loading.set(false);
      },
      error: (err) => this.handleActionError(err, "Erro ao carregar histórico do lead."),
    });
  }

  viewOpportunityHistory(opportunity: OpportunityRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.getOpportunityHistory(opportunity.id).subscribe({
      next: (payload) => {
        this.opportunityHistory.set(payload);
        this.leadHistory.set(null);
        this.loading.set(false);
      },
      error: (err) =>
        this.handleActionError(err, "Erro ao carregar histórico da oportunidade."),
    });
  }

  clearHistory(): void {
    this.leadHistory.set(null);
    this.opportunityHistory.set(null);
  }

  onActivityTargetTypeChange(nextValue: "LEAD" | "OPPORTUNITY"): void {
    this.activityTargetType.set(nextValue);
    this.activityTargetId.set("");
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

  private resetActivityForm(): void {
    this.activityKind.set("FOLLOW_UP");
    this.activityPriority.set("MEDIUM");
    this.activityTitle.set("");
    this.activityDescription.set("");
    this.activityDueAt.set("");
    this.activityReminderAt.set("");
    this.activitySlaHours.set("");
    this.activityTargetType.set("LEAD");
    this.activityTargetId.set("");
  }

  private parseLocalDateTime(localDateTime: string): string | null {
    if (!localDateTime.trim()) {
      return null;
    }
    const date = new Date(localDateTime);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    return date.toISOString();
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
