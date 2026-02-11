import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { ActivatedRoute, Router } from "@angular/router";
import { finalize } from "rxjs";

import { ToastService } from "../../core/ui/toast.service";
import { GlobalMonitoringDto, MonitoringServiceSnapshotDto } from "../../data-access/control-panel";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-monitoring-global-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatPaginatorModule,
    MatSelectModule,
    MatTableModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-monitoring-global-page.component.html",
  styleUrl: "./control-panel-monitoring-global-page.component.scss",
})
export class ControlPanelMonitoringGlobalPageComponent implements OnInit {
  private static readonly PERIODS = ["1h", "24h", "7d"] as const;

  readonly periodOptions = [
    { value: "1h", label: "Última 1h" },
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
  ] as const;

  readonly displayedServiceColumns = [
    "service_name",
    "status",
    "latency_ms",
    "error_rate",
    "captured_at",
  ];

  readonly displayedTenantColumns = [
    "tenant_name",
    "request_rate",
    "error_rate",
    "p95_latency",
    "jobs_pending",
    "last_seen_at",
    "actions",
  ];

  readonly loading = signal(false);
  readonly error = signal("");
  readonly selectedPeriod = signal<string>("24h");
  readonly tenantSearch = signal("");
  readonly serviceStatusFilter = signal<"ALL" | "GOOD" | "WARN" | "BAD">("ALL");
  readonly tenantHealthFilter = signal<"ALL" | "RISK" | "HEALTHY">("ALL");
  readonly payload = signal<GlobalMonitoringDto | null>(null);
  readonly servicesPageIndex = signal(0);
  readonly servicesPageSize = signal(10);
  readonly tenantsPageIndex = signal(0);
  readonly tenantsPageSize = signal(10);
  readonly serviceStatusOptions = [
    { value: "ALL", label: "Todos os serviços" },
    { value: "GOOD", label: "Somente saudáveis" },
    { value: "WARN", label: "Somente warning/degraded" },
    { value: "BAD", label: "Somente críticos/down" },
  ] as const;
  readonly tenantHealthOptions = [
    { value: "ALL", label: "Todos os tenants" },
    { value: "RISK", label: "Somente em risco" },
    { value: "HEALTHY", label: "Somente saudáveis" },
  ] as const;
  readonly filteredServices = computed(() => {
    const data = this.payload();
    if (!data) {
      return [];
    }
    const filter = this.serviceStatusFilter();
    if (filter === "ALL") {
      return data.services;
    }
    return data.services.filter((service) => {
      const cls = this.statusClass(service);
      if (filter === "GOOD") {
        return cls === "status-good";
      }
      if (filter === "WARN") {
        return cls === "status-warn";
      }
      return cls === "status-bad";
    });
  });
  readonly mostAccessedPages = computed(() => {
    const pages = this.payload()?.summary?.most_accessed_pages ?? [];
    return pages.map((row) => {
      if (typeof row === "string") {
        return { page: row, hits: null as number | null };
      }
      return {
        page: row.path || "-",
        hits: typeof row.count === "number" ? row.count : null,
      };
    });
  });
  readonly filteredTenants = computed(() => {
    const data = this.payload();
    if (!data) {
      return [];
    }
    const term = this.tenantSearch().trim().toLowerCase();
    if (!term) {
      return data.tenants;
    }
    return data.tenants.filter((tenant) => {
      const matchesTerm =
        tenant.tenant_name.toLowerCase().includes(term) ||
        tenant.tenant_slug.toLowerCase().includes(term) ||
        String(tenant.tenant_id).includes(term);
      if (!matchesTerm) {
        return false;
      }
      const healthFilter = this.tenantHealthFilter();
      if (healthFilter === "ALL") {
        return true;
      }
      const risky = this.isTenantAtRisk(tenant);
      return healthFilter === "RISK" ? risky : !risky;
    });
  });
  readonly pagedServices = computed(() => {
    const start = this.servicesPageIndex() * this.servicesPageSize();
    return this.filteredServices().slice(start, start + this.servicesPageSize());
  });
  readonly pagedTenants = computed(() => {
    const start = this.tenantsPageIndex() * this.tenantsPageSize();
    return this.filteredTenants().slice(start, start + this.tenantsPageSize());
  });

  constructor(
    private readonly monitoringApi: MonitoringApi,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly toast: ToastService
  ) {}

  ngOnInit(): void {
    this.hydrateFromQueryParams();
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set("");
    this.monitoringApi
      .getGlobalHealth({ period: this.selectedPeriod(), page_size: 100 })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (payload) => this.payload.set(payload),
        error: () => {
          this.error.set("Falha ao carregar monitoramento global.");
          this.payload.set(null);
          this.toast.error("Falha ao carregar monitoramento global.");
        },
      });
  }

  onPeriodChange(period: string): void {
    this.selectedPeriod.set(period || "24h");
    this.persistFiltersInUrl();
    this.reload();
  }

  onTenantSearchChange(value: string): void {
    this.tenantSearch.set(value || "");
    this.tenantsPageIndex.set(0);
    this.persistFiltersInUrl();
  }

  onServiceStatusFilterChange(value: "ALL" | "GOOD" | "WARN" | "BAD"): void {
    this.serviceStatusFilter.set(value || "ALL");
    this.servicesPageIndex.set(0);
    this.persistFiltersInUrl();
  }

  onTenantHealthFilterChange(value: "ALL" | "RISK" | "HEALTHY"): void {
    this.tenantHealthFilter.set(value || "ALL");
    this.tenantsPageIndex.set(0);
    this.persistFiltersInUrl();
  }

  statusClass(service: MonitoringServiceSnapshotDto): string {
    const normalized = (service.status || "").toUpperCase();
    if (normalized.includes("DOWN") || normalized.includes("FAIL")) {
      return "status-bad";
    }
    if (normalized.includes("WARN") || normalized.includes("DEGRADED")) {
      return "status-warn";
    }
    return "status-good";
  }

  hasData(): boolean {
    return !!this.payload();
  }

  hasEmptyData(): boolean {
    const data = this.payload();
    if (!data) {
      return false;
    }
    return data.services.length === 0 && data.tenants.length === 0;
  }

  onServicesPageChanged(event: PageEvent): void {
    this.servicesPageIndex.set(event.pageIndex);
    this.servicesPageSize.set(event.pageSize);
  }

  onTenantsPageChanged(event: PageEvent): void {
    this.tenantsPageIndex.set(event.pageIndex);
    this.tenantsPageSize.set(event.pageSize);
  }

  openTenant(tenantId: number): void {
    void this.router.navigate(["/control-panel/tenants", tenantId]);
  }

  private hydrateFromQueryParams(): void {
    const query = this.route.snapshot.queryParamMap;
    this.selectedPeriod.set(this.sanitizePeriod(query.get("period")));
    this.tenantSearch.set((query.get("tenant_search") || "").trim());
    this.serviceStatusFilter.set(this.sanitizeServiceStatus(query.get("service_status")));
    this.tenantHealthFilter.set(this.sanitizeTenantHealth(query.get("tenant_health")));
  }

  private persistFiltersInUrl(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        period: this.selectedPeriod(),
        tenant_search: this.tenantSearch() || null,
        service_status: this.serviceStatusFilter() !== "ALL" ? this.serviceStatusFilter() : null,
        tenant_health: this.tenantHealthFilter() !== "ALL" ? this.tenantHealthFilter() : null,
      },
      queryParamsHandling: "merge",
      replaceUrl: true,
    });
  }

  private sanitizePeriod(value: string | null): "1h" | "24h" | "7d" {
    if (value && (ControlPanelMonitoringGlobalPageComponent.PERIODS as readonly string[]).includes(value)) {
      return value as "1h" | "24h" | "7d";
    }
    return "24h";
  }

  private sanitizeServiceStatus(value: string | null): "ALL" | "GOOD" | "WARN" | "BAD" {
    if (value === "GOOD" || value === "WARN" || value === "BAD") {
      return value;
    }
    return "ALL";
  }

  private sanitizeTenantHealth(value: string | null): "ALL" | "RISK" | "HEALTHY" {
    if (value === "RISK" || value === "HEALTHY") {
      return value;
    }
    return "ALL";
  }

  private isTenantAtRisk(tenant: GlobalMonitoringDto["tenants"][number]): boolean {
    const staleMs = 30 * 60 * 1000;
    const now = Date.now();
    const stale = !tenant.last_seen_at || now - new Date(tenant.last_seen_at).getTime() > staleMs;
    return stale || tenant.error_rate > 0 || tenant.p95_latency > 1200 || tenant.jobs_pending > 20;
  }
}
