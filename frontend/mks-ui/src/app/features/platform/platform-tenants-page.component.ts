import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { PlatformTenantsService } from "../../core/api/platform-tenants.service";
import {
  PlatformTenantRecord,
  ProvisioningStatus,
  TenantPlan,
} from "../../core/api/platform-tenants.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-platform-tenants-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./platform-tenants-page.component.html",
  styleUrl: "./platform-tenants-page.component.scss",
})
export class PlatformTenantsPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly isPlatformAdmin = computed(
    () => this.session()?.platformAdmin === true
  );

  loading = signal(false);
  error = signal("");
  success = signal("");
  search = signal("");
  tenants = signal<PlatformTenantRecord[]>([]);

  createName = signal("");
  createTenantCode = signal("");
  createSubdomain = signal("");
  createPlan = signal<TenantPlan>("STARTER");

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
      void this.router.navigate(["/sales/flow"]);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService.listTenants(this.search()).subscribe({
      next: (rows) => {
        this.tenants.set(rows);
        this.loading.set(false);
      },
      error: (err) => this.handleError(err, "Erro ao carregar tenants do Control Plane."),
    });
  }

  createTenant(): void {
    const name = this.createName().trim();
    const tenantCode = this.createTenantCode().trim().toLowerCase();
    const subdomain = this.createSubdomain().trim().toLowerCase();
    if (!name || !tenantCode || !subdomain) {
      this.error.set("Preencha nome, tenant_code e subdomain.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .createTenant({
        name,
        tenant_code: tenantCode,
        subdomain,
        is_active: true,
        contract: {
          plan: this.createPlan(),
          status: "TRIAL",
          seats: 3,
          monthly_fee: "0.00",
        },
      })
      .subscribe({
        next: () => {
          this.createName.set("");
          this.createTenantCode.set("");
          this.createSubdomain.set("");
          this.createPlan.set("STARTER");
          this.success.set("Tenant criado no Control Plane.");
          this.load();
        },
        error: (err) => this.handleError(err, "Erro ao criar tenant."),
      });
  }

  toggleTenantActive(tenant: PlatformTenantRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .patchTenant(tenant.id, { is_active: !tenant.is_active })
      .subscribe({
        next: () => {
          this.success.set("Status do tenant atualizado.");
          this.load();
        },
        error: (err) => this.handleError(err, "Erro ao atualizar status do tenant."),
      });
  }

  setProvisionStatus(
    tenant: PlatformTenantRecord,
    status: ProvisioningStatus
  ): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .provisionTenant(tenant.id, {
        status,
        portal_url: tenant.provisioning?.portal_url ?? "",
      })
      .subscribe({
        next: () => {
          this.success.set(`Provisioning alterado para ${status}.`);
          this.load();
        },
        error: (err) => this.handleError(err, "Erro ao atualizar provisioning."),
      });
  }

  executeProvisioning(tenant: PlatformTenantRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.platformTenantsService
      .executeProvisioning(tenant.id, {
        portal_url: tenant.provisioning?.portal_url ?? "",
      })
      .subscribe({
        next: () => {
          this.success.set("Provisioning executado com sucesso.");
          this.load();
        },
        error: (err) => this.handleError(err, "Falha ao executar provisioning."),
      });
  }

  private handleError(err: unknown, fallbackMessage: string): void {
    const maybeError = err as { error?: { detail?: unknown } };
    this.error.set(
      maybeError?.error?.detail
        ? JSON.stringify(maybeError.error.detail)
        : fallbackMessage
    );
    this.loading.set(false);
  }
}
