import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router } from "@angular/router";

import { AuthService } from "../../core/api/auth.service";
import { PortalContextService } from "../../core/portal/portal-context.service";

@Component({
  selector: "app-reset-password-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./reset-password-page.component.html",
  styleUrl: "./reset-password-page.component.scss",
})
export class ResetPasswordPageComponent {
  uid = signal("");
  token = signal("");
  newPassword = signal("");
  newPasswordConfirm = signal("");
  showPassword = signal(false);
  loading = signal(false);
  error = signal("");
  success = signal("");

  readonly hostDetectedControlPlane = this.portalContextService.isControlPlanePortal();
  readonly hostDetectedTenantCode = this.portalContextService.suggestedTenantCode();
  readonly isControlPlanePortal = computed(() => this.hostDetectedControlPlane);

  constructor(
    private readonly authService: AuthService,
    private readonly portalContextService: PortalContextService,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {
    const query = this.route.snapshot.queryParamMap;
    this.uid.set(query.get("uid") ?? "");
    this.token.set(query.get("token") ?? "");
    if (!this.uid() || !this.token()) {
      this.error.set("Link de redefinição inválido ou incompleto.");
    }
  }

  submit(): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");

    if (!this.uid() || !this.token()) {
      this.error.set("Link de redefinição inválido ou incompleto.");
      this.loading.set(false);
      return;
    }

    const newPassword = this.newPassword();
    const newPasswordConfirm = this.newPasswordConfirm();
    if (!newPassword || !newPasswordConfirm) {
      this.error.set("Preencha a nova senha e a confirmação.");
      this.loading.set(false);
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      this.error.set("As senhas não conferem.");
      this.loading.set(false);
      return;
    }

    this.authService
      .confirmPasswordReset({
        uid: this.uid(),
        token: this.token(),
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      })
      .subscribe({
        next: () => {
          this.success.set("Senha atualizada. Você já pode fazer login.");
          this.loading.set(false);
        },
        error: (err) => {
          const errorMessage =
            err?.error?.detail
              ? typeof err.error.detail === "string"
                ? err.error.detail
                : JSON.stringify(err.error.detail)
              : "Falha ao redefinir senha.";
          this.error.set(errorMessage);
          this.loading.set(false);
        },
      });
  }

  goToLogin(): void {
    void this.router.navigate(["/login"]);
  }
}
