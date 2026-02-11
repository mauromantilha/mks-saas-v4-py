import { CommonModule } from "@angular/common";
import { Component, Input, OnChanges, SimpleChanges, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { catchError, finalize, forkJoin, of } from "rxjs";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";

import {
  MonitoringAlertDto,
  TenantIntegrationProvider,
  TenantIntegrationSecretRefDto,
  TenantOperationalSettingsDto,
  TenantReleaseRecordDto,
} from "../../data-access/control-panel";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { ToastService } from "../../core/ui/toast.service";
import { PermissionDirective } from "../../core/auth/permission.directive";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-governance-tab",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatTableModule,
    PermissionDirective,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
  ],
  templateUrl: "./control-panel-governance-tab.component.html",
  styleUrl: "./control-panel-governance-tab.component.scss",
})
export class ControlPanelGovernanceTabComponent implements OnChanges {
  @Input({ required: true }) tenantId!: number;

  readonly loading = signal(false);
  readonly actionLoading = signal(false);
  readonly error = signal("");

  readonly limits = signal<TenantOperationalSettingsDto | null>(null);
  readonly integrations = signal<TenantIntegrationSecretRefDto[]>([]);
  readonly releases = signal<TenantReleaseRecordDto[]>([]);
  readonly alerts = signal<MonitoringAlertDto[]>([]);
  readonly alertsFilter = signal<"OPEN" | "RESOLVED">("OPEN");

  readonly providers: Array<{ value: TenantIntegrationProvider; label: string }> = [
    { value: "SMTP", label: "SMTP" },
    { value: "WHATSAPP", label: "WhatsApp" },
    { value: "VERTEX_AI", label: "Vertex AI" },
    { value: "CUSTOM", label: "Custom" },
  ];

  readonly releaseForm = signal({
    backend_version: "",
    frontend_version: "",
    git_sha: "",
    source: "cloud_run",
    changelog: "",
  });

  readonly integrationForm = signal({
    provider: "SMTP" as TenantIntegrationProvider,
    alias: "default",
    secret_manager_ref: "",
    metadata_json: "{}",
    is_active: true,
  });

  readonly impersonationReason = signal("");
  readonly impersonationMinutes = signal(30);
  readonly impersonationSessionId = signal<number | null>(null);

  readonly integrationColumns = ["provider", "alias", "secret", "active"] as const;
  readonly releaseColumns = ["backend", "frontend", "source", "deployed", "current"] as const;
  readonly alertColumns = ["type", "severity", "message", "status", "last_seen", "actions"] as const;

  constructor(private readonly tenantApi: TenantApi, private readonly toast: ToastService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenantId"] && this.tenantId) {
      this.reload();
    }
  }

  reload(): void {
    if (!this.tenantId) {
      return;
    }
    this.loading.set(true);
    this.error.set("");

    forkJoin({
      limits: this.tenantApi.getTenantLimits(this.tenantId).pipe(catchError(() => of(null))),
      integrations: this.tenantApi.listTenantIntegrations(this.tenantId).pipe(catchError(() => of([]))),
      releases: this.tenantApi.listTenantChangelog(this.tenantId).pipe(catchError(() => of([]))),
      alerts: this.tenantApi
        .listTenantAlerts(this.tenantId, this.alertsFilter())
        .pipe(catchError(() => of([]))),
    })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: ({ limits, integrations, releases, alerts }) => {
        this.limits.set(limits || null);
          this.integrations.set(Array.isArray(integrations) ? integrations : integrations?.results || []);
          this.releases.set(Array.isArray(releases) ? releases : releases?.results || []);
          this.alerts.set(Array.isArray(alerts) ? alerts : alerts?.results || []);
        },
        error: () => {
          this.error.set("Falha ao carregar dados de governança do tenant.");
        },
      });
  }

  saveLimits(): void {
    const row = this.limits();
    if (!row || !this.tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .updateTenantLimits(this.tenantId, {
        requests_per_minute: row.requests_per_minute,
        storage_limit_gb: row.storage_limit_gb,
        docs_storage_limit_gb: row.docs_storage_limit_gb,
        module_limits_json: row.module_limits_json || {},
        current_storage_gb: row.current_storage_gb,
        current_docs_storage_gb: row.current_docs_storage_gb,
      })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: (updated) => {
          this.limits.set(updated);
          this.toast.success("Limites atualizados.");
        },
        error: () => this.toast.error("Falha ao salvar limites."),
      });
  }

  upsertIntegration(): void {
    if (!this.tenantId) {
      return;
    }
    const form = this.integrationForm();
    let metadata: Record<string, unknown> = {};
    try {
      metadata = JSON.parse(form.metadata_json || "{}");
    } catch {
      this.toast.error("Metadata JSON inválido.");
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .upsertTenantIntegration(this.tenantId, {
        provider: form.provider,
        alias: form.alias.trim() || "default",
        secret_manager_ref: form.secret_manager_ref.trim(),
        metadata_json: metadata,
        is_active: form.is_active,
      })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.toast.success("Integração salva.");
          this.reloadIntegrations();
        },
        error: () => this.toast.error("Falha ao salvar integração."),
      });
  }

  createRelease(): void {
    if (!this.tenantId) {
      return;
    }
    const form = this.releaseForm();
    if (!form.backend_version.trim()) {
      this.toast.error("Backend version é obrigatória.");
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .createTenantChangelog(this.tenantId, {
        backend_version: form.backend_version.trim(),
        frontend_version: form.frontend_version.trim(),
        git_sha: form.git_sha.trim(),
        source: form.source.trim() || "cloud_run",
        changelog: form.changelog.trim(),
        is_current: true,
      })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.toast.success("Release registrada.");
          this.releaseForm.set({
            backend_version: "",
            frontend_version: "",
            git_sha: "",
            source: "cloud_run",
            changelog: "",
          });
          this.reloadReleases();
        },
        error: () => this.toast.error("Falha ao registrar release."),
      });
  }

  onAlertsFilterChange(value: "OPEN" | "RESOLVED"): void {
    this.alertsFilter.set(value);
    this.reloadAlerts();
  }

  resolveAlert(alertId: number): void {
    if (!this.tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .resolveTenantAlert(this.tenantId, alertId)
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.toast.success("Alerta resolvido.");
          this.reloadAlerts();
        },
        error: () => this.toast.error("Falha ao resolver alerta."),
      });
  }

  exportTenantData(): void {
    if (!this.tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .exportTenantData(this.tenantId)
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: (payload) => {
          const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = `tenant-${this.tenantId}-export-${Date.now()}.json`;
          anchor.click();
          URL.revokeObjectURL(url);
          this.toast.success("Exportação concluída.");
        },
        error: () => this.toast.error("Falha ao exportar dados do tenant."),
      });
  }

  startImpersonation(): void {
    if (!this.tenantId) {
      return;
    }
    const duration = Math.max(5, Math.min(240, Number(this.impersonationMinutes()) || 30));
    this.actionLoading.set(true);
    this.tenantApi
      .startTenantImpersonation(this.tenantId, {
        reason: this.impersonationReason().trim() || undefined,
        duration_minutes: duration,
      })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: (payload) => {
          const session = payload["session"] as { id?: number } | undefined;
          this.impersonationSessionId.set(typeof session?.id === "number" ? session.id : null);
          this.toast.success("Impersonação iniciada.");
        },
        error: () => this.toast.error("Falha ao iniciar impersonação."),
      });
  }

  stopImpersonation(): void {
    if (!this.tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantApi
      .stopTenantImpersonation(this.tenantId, {
        session_id: this.impersonationSessionId() || undefined,
      })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.impersonationSessionId.set(null);
          this.toast.success("Impersonação encerrada.");
        },
        error: () => this.toast.error("Falha ao encerrar impersonação."),
      });
  }

  updateLimitsField(field: keyof TenantOperationalSettingsDto, value: string | number): void {
    const current = this.limits();
    if (!current) {
      return;
    }
    this.limits.set({
      ...current,
      [field]: value as never,
    });
  }

  patchIntegrationForm(field: "provider" | "alias" | "secret_manager_ref" | "metadata_json" | "is_active", value: string | boolean): void {
    this.integrationForm.update((current) => ({
      ...current,
      [field]: value as never,
    }));
  }

  patchReleaseForm(field: "backend_version" | "frontend_version" | "git_sha" | "source" | "changelog", value: string): void {
    this.releaseForm.update((current) => ({
      ...current,
      [field]: value,
    }));
  }

  private reloadIntegrations(): void {
    this.tenantApi.listTenantIntegrations(this.tenantId).subscribe({
      next: (rows) => this.integrations.set(Array.isArray(rows) ? rows : rows.results || []),
      error: () => this.toast.error("Falha ao recarregar integrações."),
    });
  }

  private reloadReleases(): void {
    this.tenantApi.listTenantChangelog(this.tenantId).subscribe({
      next: (rows) => this.releases.set(Array.isArray(rows) ? rows : rows.results || []),
      error: () => this.toast.error("Falha ao recarregar changelog."),
    });
  }

  private reloadAlerts(): void {
    this.tenantApi.listTenantAlerts(this.tenantId, this.alertsFilter()).subscribe({
      next: (rows) => this.alerts.set(Array.isArray(rows) ? rows : rows.results || []),
      error: () => this.toast.error("Falha ao recarregar alertas."),
    });
  }
}
