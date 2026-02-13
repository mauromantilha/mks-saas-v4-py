import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { Router } from "@angular/router";
import { forkJoin, of } from "rxjs";
import { catchError, take } from "rxjs/operators";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import { SalesMetricsRecord } from "../../core/api/sales-flow.types";
import { TenantDashboardService } from "../../core/api/tenant-dashboard.service";
import { TenantDashboardSummary } from "../../core/api/tenant-dashboard.types";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";
import { ToastService } from "../../core/ui/toast.service";
import { PrimeUiModule } from "../../shared/prime-ui.module";

type DashboardCardKind = "currency" | "number" | "text";

interface DashboardCard {
  label: string;
  value: number | string;
  hint: string;
  tone: string;
  kind: DashboardCardKind;
}

interface DashboardProductionChart {
  title: string;
  current: number;
  target: number;
  tone: string;
}

@Component({
  selector: "app-tenant-dashboard-page",
  standalone: true,
  imports: [CommonModule, PrimeUiModule],
  templateUrl: "./tenant-dashboard-page.component.html",
  styleUrl: "./tenant-dashboard-page.component.scss",
})
export class TenantDashboardPageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  private readonly decimalFormatter = new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 0,
  });

  readonly session = computed(() => this.sessionService.session());
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
  readonly permissionError = computed(() => this.permissionService.lastError());

  loading = signal(false);
  permissionsLoading = signal(true);
  error = signal("");
  notice = signal("");

  summary = signal<TenantDashboardSummary | null>(null);
  metrics = signal<SalesMetricsRecord | null>(null);

  readonly topCards = computed<DashboardCard[]>(() => {
    const kpis = this.summary()?.kpis;

    return [
      {
        label: "Produção",
        value: kpis?.production_premium_mtd ?? 0,
        hint: "Mês corrente",
        tone: "tone-green",
        kind: "currency",
      },
      {
        label: "Inadimplência",
        value: kpis?.delinquency_open_total ?? 0,
        hint: "Aberta no momento",
        tone: "tone-red",
        kind: "currency",
      },
      {
        label: "Renovações",
        value: kpis?.renewals_mtd ?? 0,
        hint: "No mês corrente",
        tone: "tone-yellow",
        kind: "number",
      },
      {
        label: "Carteira ativa",
        value: kpis?.customers_total ?? 0,
        hint: "Clientes ativos",
        tone: "tone-green",
        kind: "number",
      },
    ];
  });

  readonly operationsCards = computed<DashboardCard[]>(() => {
    const metrics = this.metrics();

    return [
      {
        label: "Baixar parcela",
        value: this.canViewFinance() ? "Em breve" : "Sem acesso",
        hint: this.canViewFinance()
          ? "Será integrado no módulo financeiro"
          : "Permissão financeira necessária",
        tone: "tone-yellow",
        kind: "text",
      },
      {
        label: "Atividades",
        value: metrics?.activities.open_total ?? 0,
        hint: "Atividades em aberto",
        tone: "tone-blue",
        kind: "number",
      },
      {
        label: "Agenda",
        value: metrics?.activities.due_today_total ?? 0,
        hint: "Compromissos do dia",
        tone: "tone-teal",
        kind: "number",
      },
    ];
  });

  readonly yearCards = computed<DashboardCard[]>(() => {
    const kpis = this.summary()?.kpis;

    return [
      {
        label: "Produção acumulada no ano",
        value: kpis?.production_premium_ytd ?? 0,
        hint: "Acumulado anual",
        tone: "tone-green",
        kind: "currency",
      },
      {
        label: "Comissão acumulada no ano",
        value: kpis?.commission_ytd ?? 0,
        hint: "Acumulado anual",
        tone: "tone-blue",
        kind: "currency",
      },
    ];
  });

  readonly monthCards = computed<DashboardCard[]>(() => {
    const kpis = this.summary()?.kpis;

    return [
      {
        label: "Produção do mês corrente",
        value: kpis?.production_premium_mtd ?? 0,
        hint: "Mês atual",
        tone: "tone-green",
        kind: "currency",
      },
      {
        label: "Comissão do mês corrente",
        value: kpis?.commission_mtd ?? 0,
        hint: "Mês atual",
        tone: "tone-orange",
        kind: "currency",
      },
    ];
  });

  readonly productionGoalCharts = computed<DashboardProductionChart[]>(() => {
    const summary = this.summary();
    const kpis = summary?.kpis;
    const goals = summary?.goals;

    return [
      {
        title: "Produção x meta anual",
        current: kpis?.production_premium_ytd ?? 0,
        target: goals?.premium_goal_ytd ?? 0,
        tone: "tone-green",
      },
      {
        title: "Produção x meta do mês",
        current: kpis?.production_premium_mtd ?? 0,
        target: goals?.premium_goal_mtd ?? 0,
        tone: "tone-blue",
      },
    ];
  });

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
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    const metrics$ = this.canViewMetrics()
      ? this.salesFlowService.getSalesMetrics().pipe(catchError(() => of(null)))
      : of(null);

    forkJoin({
      summary: this.dashboardService.getSummary(),
      metrics: metrics$,
    }).subscribe({
      next: ({ summary, metrics }) => {
        this.summary.set(summary);
        this.metrics.set(metrics ?? null);
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

  formatCardValue(card: DashboardCard): string {
    if (card.kind === "currency") {
      return this.formatCurrency(Number(card.value));
    }
    if (card.kind === "number") {
      return this.decimalFormatter.format(Number(card.value ?? 0));
    }
    return String(card.value ?? "-");
  }

  formatCurrency(value: number | null | undefined): string {
    return this.brlFormatter.format(value ?? 0);
  }

  chartWidth(value: number, current: number, target: number): number {
    const max = Math.max(current, target, 1);
    return Math.max(5, Math.round((value / max) * 100));
  }

  chartProgress(current: number, target: number): number {
    if (target <= 0) {
      return 0;
    }
    return Math.round((current / target) * 100);
  }
}
