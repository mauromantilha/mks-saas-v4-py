import { CommonModule } from "@angular/common";
import { PrimeUiModule } from "../../shared/prime-ui.module";

import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { TenantMembersService } from "../../core/api/tenant-members.service";
import {
  MembershipRole,
  TenantMember,
} from "../../core/api/tenant-members.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-members-page",
  standalone: true,
  imports: [PrimeUiModule, CommonModule, FormsModule],
  templateUrl: "./tenant-members-page.component.html",
  styleUrl: "./tenant-members-page.component.scss",
})
export class TenantMembersPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly isOwner = computed(() => this.session()?.role === "OWNER");

  loading = signal(false);
  error = signal("");
  members = signal<TenantMember[]>([]);

  newUsername = signal("");
  newRole = signal<MembershipRole>("MEMBER");

  readonly roles: MembershipRole[] = ["MEMBER", "MANAGER", "OWNER"];

  constructor(
    private readonly tenantMembersService: TenantMembersService,
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

    this.tenantMembersService.list().subscribe({
      next: (response) => {
        this.members.set(response.results);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar membros do tenant."
        );
        this.loading.set(false);
      },
    });
  }

  createOrUpdateMember(): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER pode gerenciar membros.");
      return;
    }

    const username = this.newUsername().trim();
    if (!username) {
      this.error.set("Informe o username.");
      return;
    }

    this.loading.set(true);
    this.error.set("");

    this.tenantMembersService
      .upsert({
        username,
        role: this.newRole(),
        is_active: true,
      })
      .subscribe({
        next: () => {
          this.newUsername.set("");
          this.newRole.set("MEMBER");
          this.load();
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? JSON.stringify(err.error.detail)
              : "Erro ao salvar membro."
          );
          this.loading.set(false);
        },
      });
  }

  updateRole(member: TenantMember, nextRole: MembershipRole): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER pode gerenciar membros.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.tenantMembersService.patch(member.id, { role: nextRole }).subscribe({
      next: () => this.load(),
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao atualizar papel do membro."
        );
        this.loading.set(false);
      },
    });
  }

  deactivate(member: TenantMember): void {
    if (!this.isOwner()) {
      this.error.set("Apenas OWNER pode gerenciar membros.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.tenantMembersService.deactivate(member.id).subscribe({
      next: () => this.load(),
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao desativar membro."
        );
        this.loading.set(false);
      },
    });
  }
}
