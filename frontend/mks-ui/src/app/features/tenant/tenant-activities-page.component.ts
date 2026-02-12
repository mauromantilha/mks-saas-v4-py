import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { forkJoin } from "rxjs";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  ActivityKind,
  ActivityPriority,
  AIInsightResponse,
  CommercialActivityRecord,
  LeadRecord,
  OpportunityRecord,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

type ActivityTargetType = "LEAD" | "OPPORTUNITY";

@Component({
  selector: "app-tenant-activities-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-activities-page.component.html",
  styleUrl: "./tenant-activities-page.component.scss",
})
export class TenantActivitiesPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  activities = signal<CommercialActivityRecord[]>([]);
  reminderActivities = signal<CommercialActivityRecord[]>([]);
  leads = signal<LeadRecord[]>([]);
  opportunities = signal<OpportunityRecord[]>([]);

  aiResponse = signal<AIInsightResponse | null>(null);
  aiEntityLabel = signal("");

  // Create form.
  kind = signal<ActivityKind>("FOLLOW_UP");
  priority = signal<ActivityPriority>("MEDIUM");
  title = signal("");
  description = signal("");
  dueAt = signal("");
  reminderAt = signal("");
  slaHours = signal("");
  targetType = signal<ActivityTargetType>("LEAD");
  targetId = signal("");

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
      activities: this.salesFlowService.listActivities(),
      reminders: this.salesFlowService.listReminderActivities(),
      leads: this.salesFlowService.listLeads(),
      opportunities: this.salesFlowService.listOpportunities(),
    }).subscribe({
      next: (result) => {
        this.activities.set(result.activities);
        this.reminderActivities.set(result.reminders);
        this.leads.set(result.leads);
        this.opportunities.set(result.opportunities);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar atividades."
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

    const title = this.title().trim();
    if (!title) {
      this.error.set("Título da atividade é obrigatório.");
      return;
    }

    const targetId = Number.parseInt(this.targetId(), 10);
    if (Number.isNaN(targetId)) {
      this.error.set("Selecione o lead ou oportunidade para vincular a atividade.");
      return;
    }

    const dueAt = this.parseLocalDateTime(this.dueAt());
    const reminderAt = this.parseLocalDateTime(this.reminderAt());
    if (this.reminderAt().trim() && reminderAt === null) {
      this.error.set("Data de lembrete inválida.");
      return;
    }
    if (this.dueAt().trim() && dueAt === null) {
      this.error.set("Data de vencimento inválida.");
      return;
    }

    const slaText = this.slaHours().trim();
    let slaHours: number | null = null;
    if (slaText) {
      slaHours = Number.parseInt(slaText, 10);
      if (!Number.isInteger(slaHours) || slaHours <= 0) {
        this.error.set("SLA deve ser um inteiro maior que zero.");
        return;
      }
    }

    const payload = {
      kind: this.kind(),
      title,
      description: this.description().trim(),
      priority: this.priority(),
      due_at: dueAt,
      reminder_at: reminderAt,
      sla_hours: slaHours,
      lead: this.targetType() === "LEAD" ? targetId : null,
      opportunity: this.targetType() === "OPPORTUNITY" ? targetId : null,
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService.createActivity(payload).subscribe({
      next: () => {
        this.notice.set("Atividade criada.");
        this.resetForm();
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao criar atividade."
        );
        this.loading.set(false);
      },
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
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.completeActivity(activity.id).subscribe({
      next: () => {
        this.notice.set(`Atividade #${activity.id} concluída.`);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao concluir atividade."
        );
        this.loading.set(false);
      },
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
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.reopenActivity(activity.id).subscribe({
      next: () => {
        this.notice.set(`Atividade #${activity.id} reaberta.`);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao reabrir atividade."
        );
        this.loading.set(false);
      },
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
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.markActivityReminded(activity.id).subscribe({
      next: () => {
        this.notice.set(`Lembrete enviado marcado para atividade #${activity.id}.`);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao marcar lembrete."
        );
        this.loading.set(false);
      },
    });
  }

  generateInsights(activity: CommercialActivityRecord): void {
    this.aiEntityLabel.set(`Atividade #${activity.id}`);
    this.aiResponse.set(null);
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .generateActivityAIInsights(activity.id, { include_cnpj_enrichment: true })
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

  onTargetTypeChange(nextValue: ActivityTargetType): void {
    this.targetType.set(nextValue);
    this.targetId.set("");
  }

  resetForm(): void {
    this.kind.set("FOLLOW_UP");
    this.priority.set("MEDIUM");
    this.title.set("");
    this.description.set("");
    this.dueAt.set("");
    this.reminderAt.set("");
    this.slaHours.set("");
    this.targetType.set("LEAD");
    this.targetId.set("");
  }

  private parseLocalDateTime(raw: string): string | null {
    const trimmed = raw.trim();
    if (!trimmed) {
      return null;
    }
    const date = new Date(trimmed);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    return date.toISOString();
  }
}
