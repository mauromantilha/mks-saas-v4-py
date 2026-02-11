import { CommonModule } from "@angular/common";
import { Component, Input, OnChanges, SimpleChanges, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { finalize } from "rxjs";

import {
  MonitoringAlertDto,
  MonitoringTenantSnapshotDto,
  TenantMonitoringDto,
} from "../../data-access/control-panel";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { ToastService } from "../../core/ui/toast.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-monitoring-tenant-tab",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatTableModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-monitoring-tenant-tab.component.html",
  styleUrl: "./control-panel-monitoring-tenant-tab.component.scss",
})
export class ControlPanelMonitoringTenantTabComponent implements OnChanges {
  @Input({ required: true }) tenantId!: number;

  readonly periodOptions = [
    { value: "1h", label: "Última 1h" },
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
  ] as const;

  readonly selectedPeriod = signal<string>("24h");
  readonly loading = signal(false);
  readonly error = signal("");
  readonly payload = signal<TenantMonitoringDto | null>(null);

  readonly historyColumns = ["captured_at", "request_rate", "error_rate", "p95_latency", "jobs_pending"];
  readonly incidentsColumns = ["severity", "status", "message", "last_seen_at"];

  constructor(
    private readonly monitoringApi: MonitoringApi,
    private readonly toast: ToastService
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenantId"] && this.tenantId) {
      this.reload();
    }
  }

  onPeriodChange(period: string): void {
    this.selectedPeriod.set(period || "24h");
    this.reload();
  }

  reload(): void {
    if (!this.tenantId) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.monitoringApi
      .getTenantHealth(this.tenantId, { period: this.selectedPeriod(), page_size: 100 })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (payload) => this.payload.set(payload),
        error: () => {
          this.error.set("Falha ao carregar monitoramento do tenant.");
          this.payload.set(null);
          this.toast.error("Falha ao carregar monitoramento do tenant.");
        },
      });
  }

  latest(): MonitoringTenantSnapshotDto | null {
    return this.payload()?.latest ?? null;
  }

  incidents(): MonitoringAlertDto[] {
    return this.payload()?.alerts ?? [];
  }

  hasEmptyData(): boolean {
    const data = this.payload();
    if (!data) {
      return false;
    }
    return !data.latest && data.history.length === 0 && this.incidents().length === 0;
  }
}
