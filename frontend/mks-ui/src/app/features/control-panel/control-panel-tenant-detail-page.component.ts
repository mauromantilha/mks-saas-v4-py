import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { forkJoin } from "rxjs";

import { PlatformMonitoringService } from "../../core/api/platform-monitoring.service";
import { TenantMonitoringResponse } from "../../core/api/platform-monitoring.types";
import { PlatformTenantsService } from "../../core/api/platform-tenants.service";
import {
  AdminAuditEventRecord,
  PlanRecord,
  PlatformTenantRecord,
  TenantAlertEventRecord,
  TenantContractRecord,
  TenantFeatureFlagRecord,
  TenantIntegrationSecretRefRecord,
  TenantInternalNoteRecord,
  TenantOperationalSettingsRecord,
  TenantReleaseRecord,
} from "../../core/api/platform-tenants.types";
import { PermissionDirective } from "../../core/auth/permission.directive";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";

type TenantDetailTab =
  | "overview"
  | "billing"
  | "contracts"
  | "monitoring"
  | "governance"
  | "features"
  | "notes"
  | "audit";

@Component({
  selector: "app-control-panel-tenant-detail-page",
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, PermissionDirective],
  templateUrl: "./control-panel-tenant-detail-page.component.html",
  styleUrl: "./control-panel-tenant-detail-page.component.scss",
})
export class ControlPanelTenantDetailPageComponent implements OnInit {
  readonly monitoringPeriodOptions = [
    { value: "1h", label: "Última 1 hora" },
    { value: "6h", label: "Últimas 6 horas" },
    { value: "24h", label: "Últimas 24 horas" },
    { value: "7d", label: "Últimos 7 dias" },
    { value: "30d", label: "Últimos 30 dias" },
  ] as const;

  readonly tenantId = signal<number | null>(null);
  readonly loading = signal(false);
  readonly actionLoading = signal(false);
  readonly error = signal("");
  readonly success = signal("");

  readonly tenant = signal<PlatformTenantRecord | null>(null);
  readonly plans = signal<PlanRecord[]>([]);
  readonly selectedTab = signal<TenantDetailTab>("overview");

  readonly contracts = signal<TenantContractRecord[]>([]);
  readonly selectedContract = signal<TenantContractRecord | null>(null);
  readonly monitoring = signal<TenantMonitoringResponse | null>(null);
  readonly monitoringPeriod = signal<string>("24h");
  readonly tenantLimits = signal<TenantOperationalSettingsRecord | null>(null);
  readonly tenantIntegrations = signal<TenantIntegrationSecretRefRecord[]>([]);
  readonly tenantReleases = signal<TenantReleaseRecord[]>([]);
  readonly tenantAlerts = signal<TenantAlertEventRecord[]>([]);
  readonly features = signal<TenantFeatureFlagRecord[]>([]);
  readonly notes = signal<TenantInternalNoteRecord[]>([]);
  readonly auditEvents = signal<AdminAuditEventRecord[]>([]);

  readonly contractEmail = signal("");
  readonly noteDraft = signal("");
  readonly integrationProvider = signal("RESEND");
  readonly integrationAlias = signal("default");
  readonly integrationSecretRef = signal("");
  readonly integrationMetadata = signal("{}");
  readonly integrationActive = signal(true);
  readonly releaseBackendVersion = signal("");
  readonly releaseFrontendVersion = signal("");
  readonly releaseGitSha = signal("");
  readonly releaseChangelog = signal("");
  readonly releaseSource = signal("cloud_run");
  readonly alertsFilter = signal<"OPEN" | "RESOLVED">("OPEN");

  readonly subscriptionPlanId = signal<number | null>(null);
  readonly subscriptionIsTrial = signal(false);
  readonly subscriptionTrialDays = signal(7);
  readonly subscriptionIsCourtesy = signal(false);
  readonly subscriptionSetupFeeOverride = signal<string>("");

  readonly canUnsuspend = computed(() =>
    this.permissionService.hasPermission("control_panel.superadmin")
  );

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly tenantsService: PlatformTenantsService,
    private readonly monitoringService: PlatformMonitoringService,
    private readonly permissionService: PermissionService,
    private readonly sessionService: SessionService
  ) {}

  asString(value: unknown, fallback = "0"): string {
    if (value === null || value === undefined) {
      return fallback;
    }
    return String(value);
  }

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    if (!Number.isFinite(id) || id <= 0) {
      this.error.set("ID de tenant inválido.");
      return;
    }
    this.tenantId.set(id);
    this.loadBaseData(id);
  }

  loadBaseData(tenantId: number): void {
    this.loading.set(true);
    this.clearMessages();

    forkJoin({
      tenant: this.tenantsService.getTenant(tenantId),
      plans: this.tenantsService.listPlans(),
    }).subscribe({
      next: ({ tenant, plans }) => {
        this.tenant.set(tenant);
        this.plans.set(plans);
        this.contractEmail.set(tenant.contact_email || "");
        this.syncSubscriptionState(tenant);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.handleError(err, "Falha ao carregar dados do tenant.");
      },
    });
  }

  setTab(tab: TenantDetailTab): void {
    this.selectedTab.set(tab);

    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }

    if (tab === "contracts") {
      this.loadContracts(tenantId);
      return;
    }

    if (tab === "monitoring") {
      this.loadMonitoring(tenantId, this.monitoringPeriod());
      return;
    }

    if (tab === "features") {
      this.loadFeatures(tenantId);
      return;
    }

    if (tab === "governance") {
      this.loadGovernanceResources(tenantId);
      return;
    }

    if (tab === "notes") {
      this.loadNotes(tenantId);
      return;
    }

    if (tab === "audit") {
      this.loadAudit(tenantId);
    }
  }

  saveSubscription(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    const planId = this.subscriptionPlanId();
    if (!planId) {
      this.error.set("Selecione um plano.");
      return;
    }

    const isTrial = this.subscriptionIsTrial();
    const trialDays = this.subscriptionTrialDays();
    if (isTrial && (!Number.isFinite(trialDays) || trialDays < 1 || trialDays > 90)) {
      this.error.set("Dias de trial deve estar entre 1 e 90.");
      return;
    }

    const setupFeeValue = this.subscriptionSetupFeeOverride().trim();
    if (setupFeeValue && setupFeeValue !== "0" && setupFeeValue !== "150") {
      this.error.set("Setup fee override deve ser 0 ou 150.");
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService
      .changeSubscription(tenant.id, {
        plan_id: planId,
        is_trial: isTrial,
        trial_days: isTrial ? trialDays : undefined,
        is_courtesy: this.subscriptionIsCourtesy(),
        setup_fee_override: setupFeeValue ? setupFeeValue : null,
      })
      .subscribe({
        next: (updated) => {
          this.tenant.set(updated);
          this.syncSubscriptionState(updated);
          this.success.set("Plano e cobrança atualizados com sucesso.");
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao atualizar plano/cobrança.");
        },
      });
  }

  suspendTenant(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    if (!window.confirm(`Suspender o tenant ${tenant.legal_name}?`)) {
      return;
    }

    const reason = (window.prompt("Motivo da suspensão (opcional):", "") || "").trim();
    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService.suspendTenant(tenant.id, reason).subscribe({
      next: (updated) => {
        this.tenant.set(updated);
        this.success.set("Tenant suspenso com sucesso.");
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao suspender tenant.");
      },
    });
  }

  unsuspendTenant(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    if (!window.confirm(`Reativar o tenant ${tenant.legal_name}?`)) {
      return;
    }

    const reason = (window.prompt("Motivo da reativação (opcional):", "") || "").trim();
    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService.unsuspendTenant(tenant.id, reason).subscribe({
      next: (updated) => {
        this.tenant.set(updated);
        this.success.set("Tenant reativado com sucesso.");
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao reativar tenant.");
      },
    });
  }

  softDeleteTenant(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    const typedSlug = (window.prompt(`Digite o slug para confirmar exclusão: ${tenant.slug}`) || "").trim();
    if (typedSlug !== tenant.slug) {
      this.error.set("Confirmação inválida. Digite o slug exatamente.");
      return;
    }

    const reason = (window.prompt("Motivo da exclusão lógica (obrigatório):", "") || "").trim();
    if (!reason) {
      this.error.set("Motivo é obrigatório para exclusão lógica.");
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService.softDeleteTenant(tenant.id, reason, "DELETE").subscribe({
      next: (updated) => {
        this.tenant.set(updated);
        this.success.set("Tenant marcado como DELETED.");
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao excluir tenant.");
      },
    });
  }

  exportTenantData(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService.exportTenantData(tenant.id).subscribe({
      next: (payload) => {
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `tenant-export-${tenant.slug}-${Date.now()}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.success.set("Exportação concluída.");
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao exportar dados do tenant.");
      },
    });
  }

  loadContracts(tenantId: number): void {
    this.actionLoading.set(true);
    this.tenantsService.listTenantContracts(tenantId).subscribe({
      next: (contracts) => {
        this.contracts.set(contracts);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar contratos.");
      },
    });
  }

  createContractDraft(): void {
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();
    this.tenantsService.createTenantContract(tenantId).subscribe({
      next: () => {
        this.success.set("Contrato draft criado.");
        this.loadContracts(tenantId);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao criar contrato draft.");
      },
    });
  }

  openContract(contractId: number): void {
    this.actionLoading.set(true);
    this.tenantsService.getContract(contractId).subscribe({
      next: (contract) => {
        this.selectedContract.set(contract);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar contrato.");
      },
    });
  }

  sendContract(contract: TenantContractRecord, forceSend = false): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

    const toEmail = this.contractEmail().trim() || tenant.contact_email;
    if (!toEmail) {
      this.error.set("Informe o email de destino para envio do contrato.");
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();

    this.tenantsService
      .sendContract(contract.id, { to_email: toEmail, force_send: forceSend })
      .subscribe({
        next: () => {
          this.success.set(
            forceSend ? "Contrato reenviado com sucesso." : "Contrato enviado com sucesso."
          );
          const tenantId = this.tenantId();
          if (tenantId) {
            this.loadContracts(tenantId);
          }
          this.openContract(contract.id);
        },
        error: (err) => {
          const detail = (err?.error?.detail as string | undefined) || "";
          if (!forceSend && err?.status === 409 && detail) {
            const confirmResend = window.confirm(`${detail}\nDeseja reenviar mesmo assim?`);
            if (confirmResend) {
              this.actionLoading.set(false);
              this.sendContract(contract, true);
              return;
            }
          }
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao enviar contrato.");
        },
      });
  }

  loadMonitoring(tenantId: number, period?: string): void {
    this.actionLoading.set(true);
    this.monitoringService.getTenantMonitoring(tenantId, period).subscribe({
      next: (payload) => {
        this.monitoring.set(payload);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar monitoramento.");
      },
    });
  }

  onMonitoringPeriodChange(value: string): void {
    this.monitoringPeriod.set(value || "24h");
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }
    this.loadMonitoring(tenantId, this.monitoringPeriod());
  }

  loadGovernanceResources(tenantId: number): void {
    this.actionLoading.set(true);
    forkJoin({
      limits: this.tenantsService.getTenantLimits(tenantId),
      integrations: this.tenantsService.listTenantIntegrations(tenantId),
      changelog: this.tenantsService.listTenantChangelog(tenantId),
      alerts: this.tenantsService.listTenantAlerts(tenantId, this.alertsFilter()),
    }).subscribe({
      next: ({ limits, integrations, changelog, alerts }) => {
        this.tenantLimits.set(limits);
        this.tenantIntegrations.set(integrations);
        this.tenantReleases.set(changelog);
        this.tenantAlerts.set(alerts);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar governança do tenant.");
      },
    });
  }

  saveLimits(): void {
    const tenantId = this.tenantId();
    const limits = this.tenantLimits();
    if (!tenantId || !limits) {
      return;
    }
    this.actionLoading.set(true);
    this.clearMessages();
    this.tenantsService
      .updateTenantLimits(tenantId, {
        requests_per_minute: limits.requests_per_minute,
        storage_limit_gb: limits.storage_limit_gb,
        docs_storage_limit_gb: limits.docs_storage_limit_gb,
        module_limits_json: limits.module_limits_json,
        current_storage_gb: limits.current_storage_gb,
        current_docs_storage_gb: limits.current_docs_storage_gb,
      })
      .subscribe({
        next: (updated) => {
          this.tenantLimits.set(updated);
          this.success.set("Limites atualizados com sucesso.");
          this.actionLoading.set(false);
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao atualizar limites.");
        },
      });
  }

  updateLimitsField(field: keyof TenantOperationalSettingsRecord, value: unknown): void {
    const limits = this.tenantLimits();
    if (!limits) {
      return;
    }
    this.tenantLimits.set({
      ...limits,
      [field]: value,
    });
  }

  upsertIntegration(): void {
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }
    const secretRef = this.integrationSecretRef().trim();
    if (!secretRef) {
      this.error.set("Informe a referência do Secret Manager.");
      return;
    }
    let metadata: Record<string, unknown> = {};
    const rawMetadata = this.integrationMetadata().trim();
    if (rawMetadata) {
      try {
        metadata = JSON.parse(rawMetadata) as Record<string, unknown>;
      } catch {
        this.error.set("metadata_json inválido. Use JSON válido.");
        return;
      }
    }

    this.actionLoading.set(true);
    this.clearMessages();
    this.tenantsService
      .upsertTenantIntegration(tenantId, {
        provider: this.integrationProvider(),
        alias: this.integrationAlias().trim() || "default",
        secret_manager_ref: secretRef,
        metadata_json: metadata,
        is_active: this.integrationActive(),
      })
      .subscribe({
        next: () => {
          this.success.set("Integração salva com sucesso.");
          this.loadGovernanceResources(tenantId);
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao salvar integração.");
        },
      });
  }

  createReleaseRecord(): void {
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }
    const backendVersion = this.releaseBackendVersion().trim();
    if (!backendVersion) {
      this.error.set("backend_version é obrigatório.");
      return;
    }

    this.actionLoading.set(true);
    this.clearMessages();
    this.tenantsService
      .createTenantRelease(tenantId, {
        backend_version: backendVersion,
        frontend_version: this.releaseFrontendVersion().trim(),
        git_sha: this.releaseGitSha().trim(),
        source: this.releaseSource().trim() || "cloud_run",
        changelog: this.releaseChangelog().trim(),
        is_current: true,
      })
      .subscribe({
        next: () => {
          this.success.set("Versão/changelog registrado.");
          this.releaseBackendVersion.set("");
          this.releaseFrontendVersion.set("");
          this.releaseGitSha.set("");
          this.releaseChangelog.set("");
          this.loadGovernanceResources(tenantId);
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao registrar versão/changelog.");
        },
      });
  }

  applyAlertsFilter(value: "OPEN" | "RESOLVED"): void {
    this.alertsFilter.set(value);
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantsService.listTenantAlerts(tenantId, value).subscribe({
      next: (alerts) => {
        this.tenantAlerts.set(alerts);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar alertas.");
      },
    });
  }

  resolveAlert(alertId: number): void {
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.tenantsService.resolveTenantAlert(tenantId, alertId).subscribe({
      next: () => {
        this.success.set("Alerta resolvido.");
        this.applyAlertsFilter(this.alertsFilter());
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao resolver alerta.");
      },
    });
  }

  startImpersonation(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }
    const reason = (window.prompt("Motivo da impersonação (auditoria):", "Suporte técnico") || "").trim();
    if (!reason) {
      this.error.set("Informe o motivo da impersonação.");
      return;
    }
    this.actionLoading.set(true);
    this.clearMessages();
    this.tenantsService
      .startTenantImpersonation(tenant.id, { reason, duration_minutes: 30 })
      .subscribe({
        next: (payload) => {
          this.sessionService.updateTenantContext(payload.tenant_code, "TENANT");
          this.success.set("Impersonação iniciada. Redirecionando para o portal do tenant...");
          this.actionLoading.set(false);
          void this.router.navigate(["/tenant/dashboard"]);
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao iniciar impersonação.");
        },
      });
  }

  loadFeatures(tenantId: number): void {
    this.actionLoading.set(true);
    this.tenantsService.listTenantFeatures(tenantId).subscribe({
      next: (payload) => {
        this.features.set(payload);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar features.");
      },
    });
  }

  toggleFeature(row: TenantFeatureFlagRecord): void {
    const tenantId = this.tenantId();
    if (!tenantId || !row.feature.is_active) {
      return;
    }

    this.actionLoading.set(true);
    this.tenantsService
      .updateTenantFeature(tenantId, row.feature.key, !row.enabled)
      .subscribe({
        next: () => {
          this.loadFeatures(tenantId);
          this.success.set("Feature atualizada com sucesso.");
        },
        error: (err) => {
          this.actionLoading.set(false);
          this.handleError(err, "Falha ao atualizar feature.");
        },
      });
  }

  loadNotes(tenantId: number): void {
    this.actionLoading.set(true);
    this.tenantsService.listTenantNotes(tenantId).subscribe({
      next: (payload) => {
        this.notes.set(payload);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar notas.");
      },
    });
  }

  createNote(): void {
    const tenantId = this.tenantId();
    if (!tenantId) {
      return;
    }

    const note = this.noteDraft().trim();
    if (!note) {
      this.error.set("Digite uma nota antes de salvar.");
      return;
    }

    this.actionLoading.set(true);
    this.tenantsService.createTenantNote(tenantId, note).subscribe({
      next: () => {
        this.noteDraft.set("");
        this.success.set("Nota adicionada com sucesso.");
        this.loadNotes(tenantId);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao salvar nota.");
      },
    });
  }

  loadAudit(tenantId: number): void {
    this.actionLoading.set(true);
    this.tenantsService.listTenantAudit(tenantId).subscribe({
      next: (payload) => {
        this.auditEvents.set(payload);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.actionLoading.set(false);
        this.handleError(err, "Falha ao carregar auditoria.");
      },
    });
  }

  backToTenants(): void {
    void this.router.navigate(["/control-panel/tenants"]);
  }

  planLabel(plan: PlanRecord | null | undefined): string {
    if (!plan || !plan.price) {
      return "-";
    }
    return `${plan.name} (${plan.tier}) • R$ ${plan.price.monthly_price}/mês`;
  }

  onSubscriptionSetupFeeOverrideChange(value: unknown): void {
    this.subscriptionSetupFeeOverride.set(`${value ?? ""}`);
  }

  private syncSubscriptionState(tenant: PlatformTenantRecord): void {
    const sub = tenant.subscription;
    this.subscriptionPlanId.set(sub?.plan?.id ?? this.plans()[0]?.id ?? null);
    this.subscriptionIsTrial.set(Boolean(sub?.is_trial));
    this.subscriptionTrialDays.set(sub?.is_trial ? 7 : 7);
    this.subscriptionIsCourtesy.set(Boolean(sub?.is_courtesy));
    this.subscriptionSetupFeeOverride.set(sub?.setup_fee_override ?? "");
  }

  private clearMessages(): void {
    this.error.set("");
    this.success.set("");
  }

  private handleError(err: unknown, fallback: string): void {
    const maybeErr = err as { error?: { detail?: unknown } };
    const detail = maybeErr?.error?.detail;
    if (typeof detail === "string" && detail.trim()) {
      this.error.set(detail);
      return;
    }
    if (detail !== undefined && detail !== null) {
      this.error.set(JSON.stringify(detail));
      return;
    }
    this.error.set(fallback);
  }
}
