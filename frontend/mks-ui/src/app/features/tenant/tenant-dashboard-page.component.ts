import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { forkJoin } from "rxjs";
import { catchError } from "rxjs/operators";
import { of } from "rxjs";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import { SalesMetricsRecord } from "../../core/api/sales-flow.types";
import { TenantDashboardService } from "../../core/api/tenant-dashboard.service";
import {
  TenantDashboardAIInsightsResponse,
  TenantDashboardSummary,
} from "../../core/api/tenant-dashboard.types";
import { SessionService } from "../../core/auth/session.service";
import { PrimeUiModule } from "../../shared/prime-ui.module";

@Component({
  selector: "app-tenant-dashboard-page",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    FormsModule,
    PrimeUiModule,
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
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
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

  // Goals form (current month).
  goalPremium = signal("");
  goalCommission = signal("");
  goalNewCustomers = signal("");
  goalNotes = signal("");

  constructor(
    private readonly dashboardService: TenantDashboardService,
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
    this.notice.set("");

    forkJoin({
      summary: this.dashboardService.getSummary(),
      metrics: this.salesFlowService.getSalesMetrics(),
      ai: this.dashboardService.getLatestAIInsights().pipe(
        catchError(() =>
          this.dashboardService
            .generateAIInsights({ period_days: 30 })
            .pipe(catchError(() => of(null)))
        )
      ),
    }).subscribe({
      next: ({ summary, metrics, ai }) => {
        this.summary.set(summary);
        this.metrics.set(metrics);
        this.aiInsights.set(ai);
        this.aiError.set("");
        this.goalPremium.set(String(summary.goals.premium_goal_mtd ?? 0));
        this.goalCommission.set(String(summary.goals.commission_goal_mtd ?? 0));
        this.goalNewCustomers.set(String(summary.goals.new_customers_goal_mtd ?? 0));
        this.goalNotes.set("");
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar painel do tenant."
        );
        this.loading.set(false);
      },
    });
  }

  generateWeeklyActionPlan(): void {
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
          this.aiLoading.set(false);
        },
        error: (err) => {
          this.aiError.set(err?.error?.detail || "Falha ao gerar plano de ação semanal.");
          this.aiLoading.set(false);
        },
      });
  }

  saveGoals(): void {
    const summary = this.summary();
    if (!summary) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
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
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail ? JSON.stringify(err.error.detail) : "Erro ao salvar metas."
        );
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
