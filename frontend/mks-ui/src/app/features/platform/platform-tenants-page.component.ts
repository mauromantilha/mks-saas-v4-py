import { CommonModule } from "@angular/common";
import { Component, OnDestroy, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { Subject, debounceTime, distinctUntilChanged, filter, takeUntil } from "rxjs";

import { PlatformTenantsService } from "../../core/api/platform-tenants.service";
import {
  AdminAuditEventRecord,
  PlanRecord,
  PlatformTenantRecord,
  TenantFeatureFlagRecord,
  TenantInternalNoteRecord,
} from "../../core/api/platform-tenants.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-platform-tenants-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./platform-tenants-page.component.html",
  styleUrl: "./platform-tenants-page.component.scss",
})
export class PlatformTenantsPageComponent implements OnDestroy {
  readonly session = computed(() => this.sessionService.session());
  readonly isPlatformAdmin = computed(() => this.session()?.platformAdmin === true);

  loading = signal(false);
  error = signal("");
  success = signal("");
  search = signal("");
  tenants = signal<PlatformTenantRecord[]>([]);
  plans = signal<PlanRecord[]>([]);

  createName = signal("");
  createTenantCode = signal("");
  createSubdomain = signal("");
  createCnpj = signal("");
  createPlanId = signal<number | null>(null);
  createCep = signal("");
  createStreet = signal("");
  createDistrict = signal("");
  createCity = signal("");
  createState = signal("");
  createIsTrial = signal(true);
  createTrialDays = signal(7);
  createIsCourtesy = signal(false);
  createSetupFeeOverride = signal<string | null>(null);

  billingTenantId = signal<number | null>(null);
  activeTenantTab = signal<"billing" | "audit" | "notes" | "features">("billing");
  billingPlanId = signal<number | null>(null);
  billingIsTrial = signal(false);
  billingTrialDays = signal(7);
  billingIsCourtesy = signal(false);
  billingSetupFeeOverride = signal<string | null>(null);
  detailAudit = signal<AdminAuditEventRecord[]>([]);
  detailNotes = signal<TenantInternalNoteRecord[]>([]);
  detailFeatures = signal<TenantFeatureFlagRecord[]>([]);
  detailNoteDraft = signal("");

  private readonly cepInput$ = new Subject<string>();
  private readonly destroy$ = new Subject<void>();

  constructor(
    private readonly platformTenantsService: PlatformTenantsService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    if (!this.isPlatformAdmin()) {
      void this.router.navigate(["/tenant/dashboard"]);
      return;
    }

    this.cepInput$
      .pipe(
        debounceTime(350),
        distinctUntilChanged(),
        filter((value) => value.length === 8),
        takeUntil(this.destroy$)
      )
      .subscribe((cep) => {
        this.platformTenantsService.lookupCep(cep).subscribe({
          next: (payload) => {
            this.createStreet.set(payload.logradouro || this.createStreet());
            this.createDistrict.set(payload.bairro || this.createDistrict());
            this.createCity.set(payload.cidade || this.createCity());
            this.createState.set(payload.uf || this.createState());
          },
          error: () => {
            // No-op: keep manual entry available.
          },
        });
      });

    this.loadPlans();
    this.load();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadPlans(): void {
    this.platformTenantsService.listPlans().subscribe({
      next: (rows) => {
        this.plans.set(rows);
        if (!this.createPlanId() && rows.length > 0) {
          this.createPlanId.set(rows[0].id);
        }
      },
      error: () => {
        this.error.set("Erro ao carregar planos.");
      },
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService.listTenants({ search: this.search() }).subscribe({
      next: (rows) => {
        this.tenants.set(rows);
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao carregar tenants do Control Plane."),
    });
  }

  createTenant(): void {
    const legalName = this.createName().trim();
    const slug = this.createTenantCode().trim().toLowerCase();
    const subdomain = this.createSubdomain().trim().toLowerCase();
    const planId = this.createPlanId();
    if (!legalName || !slug || !subdomain || !planId) {
      this.error.set("Preencha nome, tenant_code, subdomain e plano.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .createTenant({
        legal_name: legalName,
        cnpj: this.createCnpj().trim(),
        slug,
        subdomain,
        cep: this.createCep(),
        street: this.createStreet(),
        district: this.createDistrict(),
        city: this.createCity(),
        state: this.createState(),
        status: "ACTIVE",
      })
      .subscribe({
        next: (tenant) => {
          this.platformTenantsService
            .changeSubscription(tenant.id, {
              plan_id: planId,
              is_trial: this.createIsTrial(),
              trial_days: this.createIsTrial() ? this.createTrialDays() : undefined,
              is_courtesy: this.createIsCourtesy(),
              setup_fee_override: this.createSetupFeeOverride(),
            })
            .subscribe({
              next: () => {
                this.success.set("Tenant criado no Control Plane.");
                this.load();
              },
              error: (err) => this.handleError(err, "Tenant criado, mas falhou ao aplicar assinatura."),
            });
          this.createName.set("");
          this.createTenantCode.set("");
          this.createSubdomain.set("");
          this.createCnpj.set("");
          this.createCep.set("");
          this.createStreet.set("");
          this.createDistrict.set("");
          this.createCity.set("");
          this.createState.set("");
          this.createIsTrial.set(true);
          this.createTrialDays.set(7);
          this.createIsCourtesy.set(false);
          this.createSetupFeeOverride.set(null);
        },
        error: (err) => this.handleError(err, "Erro ao criar tenant."),
      });
  }

  onCreateCepChange(rawValue: string): void {
    const digits = (rawValue ?? "").replace(/\D/g, "").slice(0, 8);
    this.createCep.set(digits);
    if (digits.length === 8) {
      this.cepInput$.next(digits);
    }
  }

  openBillingTab(tenant: PlatformTenantRecord): void {
    this.billingTenantId.set(tenant.id);
    this.activeTenantTab.set("billing");
    this.billingPlanId.set(tenant.subscription?.plan?.id ?? this.plans()[0]?.id ?? null);
    this.billingIsTrial.set(tenant.subscription?.is_trial ?? false);
    this.billingTrialDays.set(7);
    this.billingIsCourtesy.set(tenant.subscription?.is_courtesy ?? false);
    this.billingSetupFeeOverride.set(tenant.subscription?.setup_fee_override ?? null);
  }

  openTenantTab(
    tenant: PlatformTenantRecord,
    tab: "billing" | "audit" | "notes" | "features"
  ): void {
    this.billingTenantId.set(tenant.id);
    this.activeTenantTab.set(tab);
    if (tab === "audit") {
      this.loadTenantAudit(tenant.id);
    } else if (tab === "notes") {
      this.loadTenantNotes(tenant.id);
    } else if (tab === "features") {
      this.loadTenantFeatures(tenant.id);
    } else {
      this.openBillingTab(tenant);
    }
  }

  openMonitoring(tenant: PlatformTenantRecord): void {
    void this.router.navigate(["/platform/tenants", tenant.id, "monitoring"]);
  }

  loadTenantAudit(tenantId: number): void {
    this.loading.set(true);
    this.platformTenantsService.listTenantAudit(tenantId).subscribe({
      next: (rows) => {
        this.detailAudit.set(rows);
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao carregar auditoria."),
    });
  }

  loadTenantNotes(tenantId: number): void {
    this.loading.set(true);
    this.platformTenantsService.listTenantNotes(tenantId).subscribe({
      next: (rows) => {
        this.detailNotes.set(rows);
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao carregar notas internas."),
    });
  }

  createTenantNote(tenantId: number): void {
    const note = this.detailNoteDraft().trim();
    if (!note) {
      this.error.set("Digite uma nota antes de salvar.");
      return;
    }
    this.loading.set(true);
    this.platformTenantsService.createTenantNote(tenantId, note).subscribe({
      next: () => {
        this.detailNoteDraft.set("");
        this.loadTenantNotes(tenantId);
      },
      error: (err) => this.handleError(err, "Erro ao salvar nota."),
    });
  }

  loadTenantFeatures(tenantId: number): void {
    this.loading.set(true);
    this.platformTenantsService.listTenantFeatures(tenantId).subscribe({
      next: (rows) => {
        this.detailFeatures.set(rows);
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao carregar feature flags."),
    });
  }

  toggleTenantFeature(tenantId: number, row: TenantFeatureFlagRecord): void {
    this.loading.set(true);
    this.platformTenantsService
      .updateTenantFeature(tenantId, row.feature.key, !row.enabled)
      .subscribe({
        next: () => {
          this.loadTenantFeatures(tenantId);
        },
        error: (err) => this.handleError(err, "Erro ao atualizar feature flag."),
      });
  }

  softDeleteTenant(tenant: PlatformTenantRecord): void {
    const challenge = `DELETE ${tenant.slug}`;
    const promptValue = window.prompt(
      `Confirma exclusão lógica do tenant "${tenant.legal_name}"?\nDigite exatamente: ${challenge}`
    );
    if ((promptValue || "").trim() !== challenge) {
      this.error.set("Confirmação inválida. Exclusão cancelada.");
      return;
    }
    const reason =
      window.prompt("Motivo da exclusão lógica (obrigatório):", tenant.last_status_reason || "") ||
      "";
    if (!reason.trim()) {
      this.error.set("Informe o motivo da exclusão lógica.");
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .softDeleteTenant(tenant.id, reason.trim(), "DELETE")
      .subscribe({
        next: () => {
          this.success.set("Tenant marcado como DELETED.");
          this.billingTenantId.set(null);
          this.load();
        },
        error: (err) => this.handleError(err, "Erro ao excluir tenant."),
      });
  }

  exportTenantData(tenant: PlatformTenantRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService.exportTenantData(tenant.id).subscribe({
      next: (payload) => {
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `tenant-export-${tenant.slug}-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.success.set("Export de dados do tenant concluído.");
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao exportar dados do tenant."),
    });
  }

  suspendTenant(tenant: PlatformTenantRecord): void {
    const confirmed = window.confirm(
      `Confirmar suspensão do tenant "${tenant.legal_name}"?`
    );
    if (!confirmed) {
      return;
    }
    const reason =
      window.prompt("Motivo da suspensão (opcional):", tenant.last_status_reason || "") || "";
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService.suspendTenant(tenant.id, reason).subscribe({
      next: () => {
        this.success.set("Tenant suspenso com sucesso.");
        this.load();
      },
      error: (err) => this.handleError(err, "Erro ao suspender tenant."),
    });
  }

  unsuspendTenant(tenant: PlatformTenantRecord): void {
    const confirmed = window.confirm(
      `Confirmar reativação do tenant "${tenant.legal_name}"?`
    );
    if (!confirmed) {
      return;
    }
    const reason = window.prompt("Motivo da reativação (opcional):", "") || "";
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService.unsuspendTenant(tenant.id, reason).subscribe({
      next: () => {
        this.success.set("Tenant reativado com sucesso.");
        this.load();
      },
      error: (err) => this.handleError(err, "Erro ao reativar tenant."),
    });
  }

  applySubscription(tenant: PlatformTenantRecord): void {
    if (!this.billingPlanId()) {
      this.error.set("Selecione um plano para alterar a assinatura.");
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .changeSubscription(tenant.id, {
        plan_id: this.billingPlanId()!,
        is_trial: this.billingIsTrial(),
        trial_days: this.billingIsTrial() ? this.billingTrialDays() : undefined,
        is_courtesy: this.billingIsCourtesy(),
        setup_fee_override: this.billingSetupFeeOverride(),
      })
      .subscribe({
        next: () => {
          this.success.set("Assinatura atualizada.");
          this.billingTenantId.set(null);
          this.load();
        },
        error: (err) => this.handleError(err, "Erro ao atualizar assinatura."),
      });
  }

  planLabel(plan: PlanRecord | null | undefined): string {
    if (!plan) {
      return "-";
    }
    const monthly = plan.price?.monthly_price ?? "-";
    const setup = plan.price?.setup_fee ?? "-";
    return `${plan.name} (${plan.tier}) - R$ ${monthly}/m | Setup R$ ${setup}`;
  }

  onCreateSetupFeeOverrideChange(value: unknown): void {
    this.createSetupFeeOverride.set(value ? `${value}` : null);
  }

  onBillingSetupFeeOverrideChange(value: unknown): void {
    this.billingSetupFeeOverride.set(value ? `${value}` : null);
  }

  private handleError(err: unknown, fallbackMessage: string): void {
    const maybeError = err as { error?: { detail?: unknown } };
    this.error.set(
      maybeError?.error?.detail ? JSON.stringify(maybeError.error.detail) : fallbackMessage
    );
    this.loading.set(false);
  }
}
