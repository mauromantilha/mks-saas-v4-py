import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { ActivatedRoute, Router } from "@angular/router";
import { catchError, finalize, forkJoin, map, of } from "rxjs";

import { GlobalMonitoringDto, PlanDto, TenantDto, TenantStatus } from "../../data-access/control-panel";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { ControlPanelAlertsWidgetComponent } from "./control-panel-alerts-widget.component";

type TenantTotals = {
  all: number;
  active: number;
  suspended: number;
  deleted: number;
  trial: number;
};

type DashboardSummary = {
  totalServices: number;
  monitoredTenants: number;
  riskyTenants: number;
  openAlerts: number;
  registeredTenants: number;
  activeTenants: number;
  suspendedTenants: number;
  deletedTenants: number;
  trialTenants: number;
  cloudRunStatus: string;
  databaseStatus: string;
  storageStatus: string;
  requestTraffic: number;
  loggedInUsers: number;
  databaseCount: number;
  cloudRunServices: number;
  storageBuckets: number;
  activePlans: number;
};

@Component({
  selector: "app-control-panel-dashboard-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatTableModule,
    EmptyStateComponent,
    LoadingStateComponent,
    ErrorStateComponent,
    ControlPanelAlertsWidgetComponent,
  ],
  templateUrl: "./control-panel-dashboard-page.component.html",
  styleUrl: "./control-panel-dashboard-page.component.scss",
})
export class ControlPanelDashboardPageComponent implements OnInit {
  private static readonly PERIODS = ["1h", "24h", "7d"] as const;

  readonly loading = signal(false);
  readonly error = signal("");
  readonly monitoring = signal<GlobalMonitoringDto | null>(null);
  readonly plans = signal<PlanDto[]>([]);
  readonly tenantsPreview = signal<TenantDto[]>([]);
  readonly tenantTotals = signal<TenantTotals>({
    all: 0,
    active: 0,
    suspended: 0,
    deleted: 0,
    trial: 0,
  });
  readonly lastUpdatedAt = signal<Date | null>(null);
  readonly selectedPeriod = signal<"1h" | "24h" | "7d">("24h");
  readonly tenantColumns: string[] = ["name", "slug", "status", "plan", "trial"];

  readonly heartbeatThresholdMinutes = signal(30);
  readonly errorThresholdPercent = signal(5);

  readonly periodOptions = [
    { value: "1h", label: "Última 1h" },
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
  ] as const;
  readonly summary = computed<DashboardSummary>(() => {
    const monitoring = this.monitoring();
    const summary = monitoring?.summary;
    const totals = this.tenantTotals();
    const plans = this.plans();
    return {
      totalServices: summary?.total_services ?? monitoring?.services?.length ?? 0,
      monitoredTenants: summary?.total_tenants ?? monitoring?.tenants?.length ?? totals.all,
      riskyTenants: this.riskyCount(),
      openAlerts: summary?.open_alerts ?? monitoring?.alerts?.length ?? 0,
      registeredTenants: summary?.registered_tenants ?? totals.all,
      activeTenants: summary?.active_tenants ?? totals.active,
      suspendedTenants: summary?.suspended_tenants ?? totals.suspended,
      deletedTenants: summary?.deleted_tenants ?? totals.deleted,
      trialTenants: totals.trial,
      cloudRunStatus: this.cloudStatusLabel(summary?.cloud_run_status),
      databaseStatus: this.cloudStatusLabel(summary?.database_status),
      storageStatus: this.cloudStatusLabel(summary?.storage_status),
      requestTraffic: summary?.request_traffic ?? 0,
      loggedInUsers: summary?.logged_in_users ?? 0,
      databaseCount: summary?.database_count ?? 0,
      cloudRunServices: summary?.cloud_run_services ?? 0,
      storageBuckets: summary?.storage_buckets ?? 0,
      activePlans: plans.filter((plan) => plan.is_active).length,
    };
  });

  constructor(
    private readonly monitoringApi: MonitoringApi,
    private readonly tenantApi: TenantApi,
    private readonly plansApi: PlansApi,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.hydrateFromQueryParams();
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set("");
    forkJoin({
      monitoring: this.monitoringApi
        .getGlobalHealth({ period: this.selectedPeriod(), page_size: 100 })
        .pipe(catchError(() => of(null))),
      plans: this.plansApi.listPlans().pipe(catchError(() => of([] as PlanDto[]))),
      preview: this.tenantApi
        .listTenants({ page: 1, page_size: 8 })
        .pipe(catchError(() => of({ items: [] as TenantDto[], total: 0, page: 1, page_size: 8 }))),
      totals: forkJoin({
        all: this.fetchTenantTotal(),
        active: this.fetchTenantTotal("ACTIVE"),
        suspended: this.fetchTenantTotal("SUSPENDED"),
        deleted: this.fetchTenantTotal("DELETED"),
        trial: this.fetchTenantTotal(undefined, true),
      }),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => {
          this.monitoring.set(data.monitoring);
          this.plans.set(data.plans);
          this.tenantsPreview.set(data.preview.items);
          this.tenantTotals.set(data.totals);
          this.lastUpdatedAt.set(new Date());
        },
        error: () => {
          this.error.set("Falha ao carregar dashboard do control panel.");
          this.monitoring.set(null);
          this.plans.set([]);
          this.tenantsPreview.set([]);
          this.tenantTotals.set({
            all: 0,
            active: 0,
            suspended: 0,
            deleted: 0,
            trial: 0,
          });
        },
      });
  }

  onPeriodChange(period: string): void {
    const value = (period || "24h") as "1h" | "24h" | "7d";
    this.selectedPeriod.set(value);
    this.persistFiltersInUrl();
    this.reload();
  }

  onOpenTenant(tenantId: number): void {
    void this.router.navigate(["/control-panel/tenants", tenantId]);
  }

  cloudStatusLabel(status: string | undefined): string {
    const normalized = (status || "UNKNOWN").toUpperCase();
    if (normalized.includes("UP") || normalized.includes("OK")) {
      return "Saudável";
    }
    if (normalized.includes("WARN") || normalized.includes("DEGRADED")) {
      return "Atenção";
    }
    if (normalized.includes("DOWN") || normalized.includes("FAIL")) {
      return "Crítico";
    }
    return normalized;
  }

  mostAccessedPages(): Array<{ label: string; hits: number | null }> {
    const pages = this.monitoring()?.summary?.most_accessed_pages ?? [];
    return pages.slice(0, 6).map((item) => {
      if (typeof item === "string") {
        return { label: item, hits: null };
      }
      return {
        label: item.path || "(sem rota)",
        hits: typeof item.count === "number" ? item.count : null,
      };
    });
  }

  onThresholdMinutesChange(value: number): void {
    const normalized = Number.isFinite(value) ? Math.max(1, Math.min(1440, Math.floor(value))) : 30;
    this.heartbeatThresholdMinutes.set(normalized);
    this.persistFiltersInUrl();
  }

  onErrorThresholdChange(value: number): void {
    const normalized = Number.isFinite(value) ? Math.max(0.1, Math.min(100, Number(value))) : 5;
    this.errorThresholdPercent.set(normalized);
    this.persistFiltersInUrl();
  }

  riskyCount(): number {
    const data = this.monitoring();
    if (!data) {
      return this.tenantTotals().suspended;
    }
    const nowMs = Date.now();
    const maxAgeMs = this.heartbeatThresholdMinutes() * 60 * 1000;
    const maxError = this.errorThresholdPercent();
    return data.tenants.filter((tenant) => {
      const stale =
        !tenant.last_seen_at || nowMs - new Date(tenant.last_seen_at).getTime() > maxAgeMs;
      const highError = (tenant.error_rate ?? 0) * 100 > maxError;
      return stale || highError;
    }).length;
  }

  statusBadgeClass(status: TenantStatus): string {
    if (status === "ACTIVE") {
      return "badge badge-active";
    }
    if (status === "SUSPENDED") {
      return "badge badge-suspended";
    }
    if (status === "DELETED" || status === "CANCELLED") {
      return "badge badge-inactive";
    }
    return "badge";
  }

  hasMonitoringPayload(): boolean {
    return !!this.monitoring();
  }

  private fetchTenantTotal(status?: TenantStatus, trial?: boolean) {
    return this.tenantApi
      .listTenants({
        status: status ?? "",
        trial: trial === undefined ? "" : trial,
        page: 1,
        page_size: 1,
      })
      .pipe(
        map((response) => response.total ?? 0),
        catchError(() => of(0))
      );
  }

  private hydrateFromQueryParams(): void {
    const query = this.route.snapshot.queryParamMap;
    this.selectedPeriod.set(this.sanitizePeriod(query.get("period")));
    this.heartbeatThresholdMinutes.set(this.sanitizeInt(query.get("hb"), 30, 1, 1440));
    this.errorThresholdPercent.set(this.sanitizeFloat(query.get("err"), 5, 0.1, 100));
  }

  private persistFiltersInUrl(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        period: this.selectedPeriod(),
        hb: this.heartbeatThresholdMinutes(),
        err: this.errorThresholdPercent(),
      },
      queryParamsHandling: "merge",
      replaceUrl: true,
    });
  }

  private sanitizePeriod(value: string | null): "1h" | "24h" | "7d" {
    if (value && (ControlPanelDashboardPageComponent.PERIODS as readonly string[]).includes(value)) {
      return value as "1h" | "24h" | "7d";
    }
    return "24h";
  }

  private sanitizeInt(value: string | null, fallback: number, min: number, max: number): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return Math.max(min, Math.min(max, Math.floor(parsed)));
  }

  private sanitizeFloat(value: string | null, fallback: number, min: number, max: number): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return Math.max(min, Math.min(max, parsed));
  }
}
