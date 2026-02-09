import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { AuthService } from "../../core/api/auth.service";
import { PortalContextService } from "../../core/portal/portal-context.service";

@Component({
  selector: "app-forgot-password-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./forgot-password-page.component.html",
  styleUrl: "./forgot-password-page.component.scss",
})
export class ForgotPasswordPageComponent {
  identifier = signal("");
  loading = signal(false);
  error = signal("");
  success = signal("");
  debugResetUrl = signal<string | null>(null);

  readonly hostDetectedControlPlane = this.portalContextService.isControlPlanePortal();
  readonly hostDetectedTenantCode = this.portalContextService.suggestedTenantCode();
  readonly isControlPlanePortal = computed(() => this.hostDetectedControlPlane);

  constructor(
    private readonly authService: AuthService,
    private readonly portalContextService: PortalContextService,
    private readonly router: Router
  ) {}

  submit(): void {
    this.loading.set(true);
    this.error.set("");
    this.success.set("");
    this.debugResetUrl.set(null);

    const raw = this.identifier().trim();
    if (!raw) {
      this.error.set("Informe seu email ou username.");
      this.loading.set(false);
      return;
    }

    const payload = raw.includes("@") ? { email: raw } : { username: raw };
    this.authService.requestPasswordReset(payload).subscribe({
      next: (response) => {
        this.success.set(
          "Se a conta existir, você receberá um link para redefinir sua senha em instantes."
        );
        if (response.reset_url) {
          this.debugResetUrl.set(response.reset_url);
        }
        this.loading.set(false);
      },
      error: (err) => {
        const errorMessage =
          err?.error?.detail
            ? typeof err.error.detail === "string"
              ? err.error.detail
              : JSON.stringify(err.error.detail)
            : "Falha ao solicitar redefinição de senha.";
        this.error.set(errorMessage);
        this.loading.set(false);
      },
    });
  }

  backToLogin(): void {
    void this.router.navigate(["/login"]);
  }
}
