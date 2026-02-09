import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { InsuranceCoreService } from "../../core/api/insurance-core.service";
import {
  CreateInsurerPayload,
  InsurerIntegrationType,
  InsurerRecord,
  InsurerStatus,
  UpdateInsurerPayload,
} from "../../core/api/insurance-core.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-insurers-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./tenant-insurers-page.component.html",
  styleUrl: "./tenant-insurers-page.component.scss",
})
export class TenantInsurersPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  search = signal("");
  statusFilter = signal<InsurerStatus | "">("");

  insurers = signal<InsurerRecord[]>([]);

  // Create form.
  name = signal("");
  legalName = signal("");
  cnpj = signal("");
  integrationType = signal<InsurerIntegrationType>("NONE");

  // Edit state.
  editing = signal<InsurerRecord | null>(null);
  editName = signal("");
  editLegalName = signal("");
  editCnpj = signal("");
  editStatus = signal<InsurerStatus>("ACTIVE");
  editIntegrationType = signal<InsurerIntegrationType>("NONE");

  readonly integrationTypes: { label: string; value: InsurerIntegrationType }[] = [
    { label: "Nenhuma", value: "NONE" },
    { label: "API", value: "API" },
    { label: "Manual", value: "MANUAL" },
    { label: "Portal Corretor", value: "BROKER_PORTAL" },
  ];

  constructor(
    private readonly insuranceCoreService: InsuranceCoreService,
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
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService
      .listInsurers({
        q: this.search(),
        status: this.statusFilter(),
      })
      .subscribe({
        next: (rows) => {
          this.insurers.set(rows);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? typeof err.error.detail === "string"
                ? err.error.detail
                : JSON.stringify(err.error.detail)
              : "Erro ao carregar seguradoras."
          );
          this.loading.set(false);
        },
      });
  }

  createInsurer(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const payload: CreateInsurerPayload = {
      name: this.name().trim(),
      legal_name: this.legalName().trim() || undefined,
      cnpj: this.cnpj().trim() || undefined,
      integration_type: this.integrationType(),
      status: "ACTIVE",
      integration_config: {},
    };

    if (!payload.name) {
      this.error.set("Nome é obrigatório.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.createInsurer(payload).subscribe({
      next: (created) => {
        this.notice.set(`Seguradora #${created.id} criada.`);
        this.resetCreateForm();
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao criar seguradora."
        );
        this.loading.set(false);
      },
    });
  }

  startEdit(insurer: InsurerRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.editing.set(insurer);
    this.editName.set(insurer.name);
    this.editLegalName.set(insurer.legal_name ?? "");
    this.editCnpj.set(insurer.cnpj ?? "");
    this.editStatus.set(insurer.status);
    this.editIntegrationType.set(insurer.integration_type);
    this.notice.set("");
    this.error.set("");
  }

  cancelEdit(): void {
    this.editing.set(null);
  }

  saveEdit(): void {
    const insurer = this.editing();
    if (!insurer) {
      return;
    }
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const payload: UpdateInsurerPayload = {
      name: this.editName().trim(),
      legal_name: this.editLegalName().trim() || "",
      cnpj: this.editCnpj().trim() || "",
      status: this.editStatus(),
      integration_type: this.editIntegrationType(),
    };

    if (!payload.name) {
      this.error.set("Nome é obrigatório.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.updateInsurer(insurer.id, payload).subscribe({
      next: () => {
        this.notice.set("Seguradora atualizada.");
        this.editing.set(null);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao atualizar seguradora."
        );
        this.loading.set(false);
      },
    });
  }

  deactivate(insurer: InsurerRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (insurer.status === "INACTIVE") {
      this.notice.set("Seguradora já está inativa.");
      return;
    }

    const confirmed = window.confirm(
      `Desativar a seguradora \"${insurer.name}\"?`
    );
    if (!confirmed) {
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.insuranceCoreService.deactivateInsurer(insurer.id).subscribe({
      next: () => {
        this.notice.set("Seguradora desativada.");
        this.editing.set(null);
        this.load();
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Erro ao desativar seguradora."
        );
        this.loading.set(false);
      },
    });
  }

  private resetCreateForm(): void {
    this.name.set("");
    this.legalName.set("");
    this.cnpj.set("");
    this.integrationType.set("NONE");
  }
}

