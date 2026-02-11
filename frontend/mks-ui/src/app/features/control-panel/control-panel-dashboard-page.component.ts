import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { ActivatedRoute, Router } from "@angular/router";
import { finalize } from "rxjs";

import { GlobalMonitoringDto } from "../../data-access/control-panel";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { ControlPanelAlertsWidgetComponent } from "./control-panel-alerts-widget.component";

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
  readonly selectedPeriod = signal<"1h" | "24h" | "7d">("24h");

  readonly heartbeatThresholdMinutes = signal(30);
  readonly errorThresholdPercent = signal(5);

  readonly periodOptions = [
    { value: "1h", label: "Última 1h" },
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
  ] as const;

  constructor(
    private readonly monitoringApi: MonitoringApi,
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
    this.monitoringApi
      .getGlobalHealth({ period: this.selectedPeriod(), page_size: 100 })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (data) => this.monitoring.set(data),
        error: () => {
          this.error.set("Falha ao carregar dashboard do control panel.");
          this.monitoring.set(null);
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
      return 0;
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
