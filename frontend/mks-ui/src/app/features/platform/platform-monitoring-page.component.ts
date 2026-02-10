import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";

import { PlatformMonitoringService } from "../../core/api/platform-monitoring.service";
import {
  ControlPanelMonitoringResponse,
  MonitoringServiceSnapshot,
  MonitoringTenantSnapshot,
} from "../../core/api/platform-monitoring.types";

@Component({
  selector: "app-platform-monitoring-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./platform-monitoring-page.component.html",
  styleUrl: "./platform-monitoring-page.component.scss",
})
export class PlatformMonitoringPageComponent implements OnInit {
  readonly periodOptions = [
    { value: "1h", label: "Última 1 hora" },
    { value: "6h", label: "Últimas 6 horas" },
    { value: "24h", label: "Últimas 24 horas" },
    { value: "7d", label: "Últimos 7 dias" },
    { value: "30d", label: "Últimos 30 dias" },
  ] as const;

  selectedPeriod = signal<string>("24h");
  loading = signal(true);
  error = signal("");
  payload = signal<ControlPanelMonitoringResponse | null>(null);

  constructor(private readonly monitoringService: PlatformMonitoringService) {}

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set("");
    this.monitoringService.getMonitoring(this.selectedPeriod()).subscribe({
      next: (payload) => {
        this.payload.set(payload);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Falha ao carregar monitoramento.");
        this.loading.set(false);
      },
    });
  }

  onPeriodChange(value: string): void {
    this.selectedPeriod.set(value || "24h");
    this.reload();
  }

  statusClass(status: string): string {
    const normalized = (status || "").toUpperCase();
    if (normalized.includes("DOWN") || normalized.includes("FAIL")) {
      return "is-down";
    }
    if (normalized.includes("WARN") || normalized.includes("DEGRADED")) {
      return "is-warn";
    }
    return "is-up";
  }

  trackService = (_index: number, row: MonitoringServiceSnapshot): string =>
    `${row.service_name}-${row.captured_at}`;

  trackTenant = (_index: number, row: MonitoringTenantSnapshot): string =>
    `${row.tenant_id}-${row.captured_at}`;
}
