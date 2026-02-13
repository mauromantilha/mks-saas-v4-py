import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { forkJoin } from "rxjs";
import { catchError } from "rxjs/operators";
import { of } from "rxjs";
import { take } from "rxjs/operators";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import { SalesMetricsRecord } from "../../core/api/sales-flow.types";
import { TenantDashboardService } from "../../core/api/tenant-dashboard.service";
import { DashboardAiSuggestionsCardComponent } from "./dashboard-ai-suggestions-card.component";
import {
  TenantDashboardAIInsightsResponse,
  TenantDashboardSummary,
} from "../../core/api/tenant-dashboard.types";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";
import { ToastService } from "../../core/ui/toast.service";
import { PrimeUiModule } from "../../shared/prime-ui.module";

@Component({
  selector: "app-tenant-dashboard-page",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    FormsModule,
    PrimeUiModule,
    DashboardAiSuggestionsCardComponent,
  ],
  templateUrl: "./tenant-dashboard-page.component.html",
  styleUrl: "./tenant-dashboard-page.component.scss",
})
export class TenantDashboardPageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => this.canViewGoals());
  readonly canViewDashboard = computed(() =>
    this.permissionService.can("tenant.dashboard.view")
  );
  readonly canViewMetrics = computed(
    () =>
      this.permissionService.can("tenant.leads.view")
      || this.permissionService.can("tenant.opportunities.view")
      || this.permissionService.can("tenant.activities.view")
  );
  readonly canViewFinance = computed(
    () =>
      this.permissionService.can("tenant.finance.view")
      || this.permissionService.can("tenant.fiscal.view")
  );
  readonly canViewGoals = computed(() => {
    const role = this.session()?.role;
    const roleAllowsWrite = role === "OWNER" || role === "MANAGER";
    return roleAllowsWrite
      && (
        this.permissionService.can("tenant.role.owner")
        || this.permissionService.can("tenant.role.manager")
      );
  });
  readonly canViewAI = computed(() =>
    this.permissionService.can("tenant.ai_assistant.view")
  );
  readonly canUseAISuggestions = computed(() =>
    this.permissionService.can("tenant.ai.use")
  );
  readonly permissionError = computed(() => this.permissionService.lastError());

  loading = signal(false);
  permissionsLoading = signal(true);
  error = signal("");
  notice = signal("");

  summary = signal<TenantDashboardSummary | null>(null);
  metrics = signal<SalesMetricsRecord | null>(null);
  aiInsights = signal<TenantDashboardAIInsightsResponse | null>(null);
  aiLoading = signal(false);
  aiError = signal("");

  readonly dailySeries = computed(() => this.summary()?.series.daily_mtd ?? []);
  readonly monthlySeries = computed(() => this.summary()?.series.monthly_ytd ?? []);
  readonly dailyMaxPremium = computed(() => this.maxOf(this.dailySeries(), "premium_total"));
  readonly monthlyMaxPremium = computed(() =>
    this.maxOf(this.monthlySeries(), "premium_total")
  );
  readonly goalRows = computed(() => {
    const summary = this.summary();
    if (!summary) {
      return [];
    }
    return [
      {
        label: "Produção (Mês)",
        target: summary.goals.premium_goal_mtd,
        current: summary.kpis.production_premium_mtd,
        progress: summary.progress.premium_mtd_pct,
      },
      {
        label: "Comissão (Mês)",
        target: summary.goals.commission_goal_mtd,
        current: summary.kpis.commission_mtd,
        progress: summary.progress.commission_mtd_pct,
      },
      {
        label: "Produção (Ano)",
        target: summary.goals.premium_goal_ytd,
        current: summary.kpis.production_premium_ytd,
        progress: summary.progress.premium_ytd_pct,
      },
      {
        label: "Comissão (Ano)",
        target: summary.goals.commission_goal_ytd,
        current: summary.kpis.commission_ytd,
        progress: summary.progress.commission_ytd_pct,
      },
    ];
  });
  readonly activityRows = computed(() => {
    const metrics = this.metrics();
    if (!metrics) {
      return [];
    }
    return [
      { label: "Atividades em aberto", value: metrics.activities.open_total },
      { label: "Vencidas", value: metrics.activities.overdue_total },
      { label: "Vencem hoje", value: metrics.activities.due_today_total },
      { label: "Lembretes hoje", value: metrics.activities.reminders_due_total },
      { label: "SLA estourado", value: metrics.activities.sla_breached_total },
    ];
  });

  // Goals form (current month).
  goalPremium = signal("");
  goalCommission = signal("");
  goalNewCustomers = signal("");
  goalNotes = signal("");

  constructor(
    private readonly dashboardService: TenantDashboardService,
    private readonly salesFlowService: SalesFlowService,
    private readonly permissionService: PermissionService,
    private readonly sessionService: SessionService,
    private readonly toast: ToastService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.permissionService.loadPermissions().pipe(take(1)).subscribe({
      next: () => {
        this.permissionsLoading.set(false);
        if (!this.canViewDashboard()) {
          this.error.set("Você não possui permissão para visualizar o dashboard.");
          this.notice.set(
            this.permissionError()
              ?? "Capacidades indisponíveis. Acesso ao dashboard bloqueado por segurança."
          );
          return;
        }
        this.load();
      },
      error: () => {
        this.permissionsLoading.set(false);
        this.error.set("Não foi possível validar permissões do dashboard.");
        this.notice.set("Acesso ao dashboard bloqueado por segurança.");
        this.toast.error("Falha ao validar permissões.");
      },
    });
  }

  load(): void {
    if (!this.canViewDashboard()) {
      this.loading.set(false);
      this.summary.set(null);
      this.metrics.set(null);
      this.aiInsights.set(null);
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    const metrics$ = this.canViewMetrics()
      ? this.salesFlowService.getSalesMetrics().pipe(catchError(() => of(null)))
      : of(null);
    const ai$ = this.canViewAI()
      ? this.dashboardService.getLatestAIInsights().pipe(
          catchError(() =>
            this.dashboardService
              .generateAIInsights({ period_days: 30 })
              .pipe(catchError(() => of(null)))
          )
        )
      : of(null);

    forkJoin({
      summary: this.dashboardService.getSummary(),
      metrics: metrics$,
      ai: ai$,
    }).subscribe({
      next: ({ summary, metrics, ai }) => {
        this.summary.set(summary);
        this.metrics.set(metrics ?? null);
        this.aiInsights.set(ai);
        this.aiError.set("");
        this.goalPremium.set(String(summary.goals.premium_goal_mtd ?? 0));
        this.goalCommission.set(String(summary.goals.commission_goal_mtd ?? 0));
        this.goalNewCustomers.set(String(summary.goals.new_customers_goal_mtd ?? 0));
        this.goalNotes.set("");
        if (!summary) {
          this.notice.set("Sem dados de dashboard para o período atual.");
        }
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar painel do tenant."
        );
        this.toast.error("Falha ao carregar dados do dashboard.");
        this.loading.set(false);
      },
    });
  }

  generateWeeklyActionPlan(): void {
    if (!this.canViewAI()) {
      this.toast.warning("Seu perfil não possui acesso ao assistente de IA.");
      return;
    }

    this.aiLoading.set(true);
    this.aiError.set("");
    this.dashboardService
      .generateAIInsights({
        period_days: 7,
        weekly_plan: true,
        focus:
          "Monte um plano de ação semanal para corretora de seguros com prioridades comerciais, financeiras e operacionais.",
      })
      .subscribe({
        next: (ai) => {
          this.aiInsights.set(ai);
          this.notice.set("Plano de ação semanal atualizado.");
          this.toast.success("Plano semanal gerado com sucesso.");
          this.aiLoading.set(false);
        },
        error: (err) => {
          this.aiError.set(err?.error?.detail || "Falha ao gerar plano de ação semanal.");
          this.toast.error("Falha ao gerar plano de ação semanal.");
          this.aiLoading.set(false);
        },
      });
  }

  saveGoals(): void {
    const summary = this.summary();
    if (!summary) {
      return;
    }
    if (!this.canViewGoals()) {
      this.error.set("Seu perfil é somente leitura.");
      this.toast.warning("Seu perfil não permite editar metas.");
      return;
    }

    const year = summary.period.year;
    const month = summary.period.month;
    const premiumGoal = this.goalPremium().trim();
    const commissionGoal = this.goalCommission().trim();
    const newCustomers = Number.parseInt(this.goalNewCustomers().trim() || "0", 10);
    if (Number.isNaN(newCustomers) || newCustomers < 0) {
      this.error.set("Meta de novos clientes deve ser um número inteiro >= 0.");
      return;
    }

    const payload = {
      year,
      month,
      premium_goal: premiumGoal || 0,
      commission_goal: commissionGoal || 0,
      new_customers_goal: newCustomers,
      notes: this.goalNotes().trim() || undefined,
    };

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    const existingId = summary.goals.sales_goal_id_mtd;
    const request$ = existingId
      ? this.dashboardService.updateSalesGoal(existingId, payload)
      : this.dashboardService.createSalesGoal(payload);

    request$.subscribe({
      next: () => {
        this.notice.set("Metas do mês atualizadas.");
        this.toast.success("Metas salvas com sucesso.");
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao salvar metas."
        );
        this.toast.error("Erro ao salvar metas.");
        this.loading.set(false);
      },
    });
  }

  formatCurrency(value: number | null | undefined): string {
    return this.brlFormatter.format(value ?? 0);
  }

  clampPct(value: number | null | undefined): number {
    const resolved = Number.isFinite(value as number) ? (value as number) : 0;
    return Math.max(0, Math.min(100, resolved));
  }

  barHeight(value: number, max: number): number {
    if (!max || max <= 0) {
      return 0;
    }
    return Math.max(2, Math.round((value / max) * 100));
  }

  private maxOf<T extends object>(rows: T[], key: keyof T): number {
    if (!rows.length) {
      return 1;
    }
    const values = rows
      .map((row) => Number((row as any)[key] ?? 0))
      .filter((value) => Number.isFinite(value));
    return Math.max(...values, 1);
  }
}
