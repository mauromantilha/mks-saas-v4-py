import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, RouterLink } from "@angular/router";

import { PlatformMonitoringService } from "../../core/api/platform-monitoring.service";
import { TenantMonitoringResponse } from "../../core/api/platform-monitoring.types";

@Component({
  selector: "app-platform-tenant-monitoring-page",
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: "./platform-tenant-monitoring-page.component.html",
  styleUrl: "./platform-tenant-monitoring-page.component.scss",
})
export class PlatformTenantMonitoringPageComponent implements OnInit {
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
  payload = signal<TenantMonitoringResponse | null>(null);
  tenantId = 0;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly monitoringService: PlatformMonitoringService
  ) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    if (!Number.isFinite(id) || id <= 0) {
      this.error.set("Tenant inválido.");
      this.loading.set(false);
      return;
    }
    this.tenantId = id;
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set("");
    this.monitoringService
      .getTenantMonitoring(this.tenantId, this.selectedPeriod())
      .subscribe({
      next: (payload) => {
        this.payload.set(payload);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Falha ao carregar monitoramento do tenant.");
        this.loading.set(false);
      },
    });
  }

  onPeriodChange(value: string): void {
    this.selectedPeriod.set(value || "24h");
    this.reload();
  }
}
