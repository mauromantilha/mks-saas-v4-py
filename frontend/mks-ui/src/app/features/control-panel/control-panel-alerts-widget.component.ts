import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, Output, computed, signal } from "@angular/core";
import { HttpErrorResponse } from "@angular/common/http";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatTableModule } from "@angular/material/table";
import { finalize } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import {
  GlobalMonitoringDto,
  MonitoringAlertDto,
  MonitoringTenantSnapshotDto,
} from "../../data-access/control-panel";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";

interface RiskTenantRow {
  tenantId: number;
  tenantName: string;
  tenantSlug: string;
  lastSeenAt: string | null;
  errorRatePercent: number;
  reasons: string[];
  alerts: MonitoringAlertDto[];
}

@Component({
  selector: "app-control-panel-alerts-widget",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    PermissionDirective,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-alerts-widget.component.html",
  styleUrl: "./control-panel-alerts-widget.component.scss",
})
export class ControlPanelAlertsWidgetComponent {
  @Input() monitoring: GlobalMonitoringDto | null = null;
  @Input() heartbeatThresholdMinutes = 30;
  @Input() errorRateThresholdPercent = 5;

  @Output() openTenant = new EventEmitter<number>();
  @Output() refreshRequested = new EventEmitter<void>();

  readonly displayedColumns = ["tenant", "heartbeat", "error_rate", "reasons", "actions"];
  readonly actionLoading = signal<Record<number, boolean>>({});

  readonly riskRows = computed<RiskTenantRow[]>(() => {
    const data = this.monitoring;
    if (!data) {
      return [];
    }

    const alertByTenant = new Map<number, MonitoringAlertDto[]>();
    (data.alerts ?? []).forEach((alert) => {
      const current = alertByTenant.get(alert.tenant) ?? [];
      current.push(alert);
      alertByTenant.set(alert.tenant, current);
    });

    const nowMs = Date.now();
    const maxHeartbeatGapMs = this.heartbeatThresholdMinutes * 60 * 1000;

    const risky: RiskTenantRow[] = [];
    for (const tenant of data.tenants) {
      const reasons: string[] = [];
      const alerts = (alertByTenant.get(tenant.tenant_id) ?? []).filter(
        (alert) => !alert.resolved_at
      );

      if (!tenant.last_seen_at) {
        reasons.push("Sem heartbeat recente");
      } else {
        const ageMs = nowMs - new Date(tenant.last_seen_at).getTime();
        if (Number.isFinite(ageMs) && ageMs > maxHeartbeatGapMs) {
          reasons.push(`Heartbeat acima de ${this.heartbeatThresholdMinutes} min`);
        }
      }

      const errorRatePercent = (tenant.error_rate ?? 0) * 100;
      if (errorRatePercent > this.errorRateThresholdPercent) {
        reasons.push(`Error rate acima de ${this.errorRateThresholdPercent}%`);
      }

      if (alerts.length > 0) {
        reasons.push(`${alerts.length} alerta(s) aberto(s)`);
      }

      if (reasons.length > 0) {
        risky.push(this.toRiskRow(tenant, reasons, alerts));
      }
    }

    return risky.sort((a, b) => b.errorRatePercent - a.errorRatePercent);
  });

  constructor(
    private readonly monitoringApi: MonitoringApi,
    private readonly toast: ToastService
  ) {}

  openTenantDetail(tenantId: number): void {
    this.openTenant.emit(tenantId);
  }

  acknowledgeFirstAlert(row: RiskTenantRow): void {
    const alert = row.alerts[0];
    if (!alert) {
      return;
    }

    this.setAlertLoading(alert.id, true);
    this.monitoringApi
      .acknowledgeAlert(alert.id)
      .pipe(finalize(() => this.setAlertLoading(alert.id, false)))
      .subscribe({
        next: () => {
          this.toast.success("Alerta reconhecido (ACK).");
          this.refreshRequested.emit();
        },
        error: (error: unknown) => {
          const httpError = error as HttpErrorResponse;
          if (httpError?.status === 404 || httpError?.status === 405) {
            this.toast.info("ACK ainda não disponível no backend.");
            return;
          }
          this.toast.error("Falha ao reconhecer alerta.");
        },
      });
  }

  hasRiskRows(): boolean {
    return this.riskRows().length > 0;
  }

  rowReasonLabel(row: RiskTenantRow): string {
    return row.reasons.join(" • ");
  }

  hasAckableAlert(row: RiskTenantRow): boolean {
    return row.alerts.length > 0;
  }

  isAlertLoading(alertId: number): boolean {
    return !!this.actionLoading()[alertId];
  }

  private setAlertLoading(alertId: number, value: boolean): void {
    this.actionLoading.update((state) => ({ ...state, [alertId]: value }));
  }

  private toRiskRow(
    tenant: MonitoringTenantSnapshotDto,
    reasons: string[],
    alerts: MonitoringAlertDto[]
  ): RiskTenantRow {
    return {
      tenantId: tenant.tenant_id,
      tenantName: tenant.tenant_name,
      tenantSlug: tenant.tenant_slug,
      lastSeenAt: tenant.last_seen_at,
      errorRatePercent: (tenant.error_rate ?? 0) * 100,
      reasons,
      alerts,
    };
  }
}

