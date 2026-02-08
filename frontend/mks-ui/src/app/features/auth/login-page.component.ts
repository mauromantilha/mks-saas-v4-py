import { CommonModule } from "@angular/common";
import { Component, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { map, switchMap } from "rxjs";

import { AuthService } from "../../core/api/auth.service";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-login-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./login-page.component.html",
  styleUrl: "./login-page.component.scss",
})
export class LoginPageComponent {
  username = signal("");
  password = signal("");
  tenantCode = signal("acme");
  loading = signal(false);
  error = signal("");

  constructor(
    private readonly authService: AuthService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/tenant/rbac"]);
    }
  }

  login(): void {
    this.loading.set(true);
    this.error.set("");

    const username = this.username().trim();
    const password = this.password();
    const tenantCode = this.tenantCode().trim().toLowerCase();

    if (!username || !password || !tenantCode) {
      this.error.set("Preencha username, password e tenant code.");
      this.loading.set(false);
      return;
    }

    this.authService
      .obtainToken(username, password)
      .pipe(
        switchMap((tokenResponse) =>
          this.authService
            .getTenantMe(tenantCode, tokenResponse.token)
            .pipe(map((tenantMe) => ({ token: tokenResponse.token, tenantMe })))
        )
      )
      .subscribe({
        next: ({ token, tenantMe }) => {
          this.sessionService.saveSession({
            token,
            tenantCode: tenantMe.tenant_code,
            username: tenantMe.username,
            role: tenantMe.role,
          });
          this.loading.set(false);
          void this.router.navigate(["/tenant/rbac"]);
        },
        error: (err) => {
          this.error.set(
            err?.error?.detail
              ? JSON.stringify(err.error.detail)
              : "Falha de autenticação ou membership para o tenant."
          );
          this.loading.set(false);
        },
      });
  }
}
