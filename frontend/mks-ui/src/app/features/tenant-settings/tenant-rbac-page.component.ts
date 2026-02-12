import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { forkJoin } from "rxjs";
import { Router } from "@angular/router";

import { AuthService } from "../../core/api/auth.service";
import { TenantRbacService } from "../../core/api/tenant-rbac.service";
import { TenantUserRole } from "../../core/api/auth.types";
import { SessionService } from "../../core/auth/session.service";
import {
  TenantRbacOverrides,
  TenantRbacResponse,
} from "../../core/api/tenant-rbac.types";

@Component({
  selector: "app-tenant-rbac-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-rbac-page.component.html",
})
export class TenantRbacPageComponent {
  loading = signal(false);
  error = signal("");
  role = signal<TenantUserRole>(null);
  payload = signal<TenantRbacResponse | null>(null);
  readonly canEdit = computed(() => this.role() === "OWNER");
  readonly session = computed(() => this.sessionService.session());

  // JSON livre para permitir edição rápida do override por OWNER.
  editJson = signal(
    JSON.stringify(
      {
        apolices: {
          POST: ["OWNER", "MANAGER"],
        },
      },
      null,
      2
    )
  );

  constructor(
    private readonly tenantRbacService: TenantRbacService,
    private readonly authService: AuthService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.load();
  }

  load(): void {
    if (!this.sessionService.isAuthenticated()) {
      this.error.set("Sessão expirada. Faça login novamente.");
      void this.router.navigate(["/login"]);
      return;
    }

    this.loading.set(true);
    this.error.set("");

    forkJoin({
      rbac: this.tenantRbacService.getTenantRbac(),
      capabilities: this.authService.getTenantCapabilities(),
    }).subscribe({
      next: (response) => {
        this.payload.set(response.rbac);
        this.role.set(response.capabilities.role);
        this.sessionService.updateRole(response.capabilities.role);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar RBAC do tenant."
        );
        this.loading.set(false);
      },
    });
  }

  saveReplace(): void {
    this.save("put");
  }

  savePatch(): void {
    this.save("patch");
  }

  private save(mode: "put" | "patch"): void {
    if (!this.canEdit()) {
      this.error.set("Apenas OWNER pode editar RBAC.");
      return;
    }

    this.loading.set(true);
    this.error.set("");

    let overrides: TenantRbacOverrides;
    try {
      overrides = JSON.parse(this.editJson());
    } catch {
      this.error.set("JSON inválido para rbac_overrides.");
      this.loading.set(false);
      return;
    }

    const request$ =
      mode === "put"
        ? this.tenantRbacService.replaceTenantRbac(overrides)
        : this.tenantRbacService.patchTenantRbac(overrides);

    request$.subscribe({
      next: (response) => {
        this.payload.set(response);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao salvar RBAC do tenant."
        );
        this.loading.set(false);
      },
    });
  }
}
