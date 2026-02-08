import { CommonModule } from "@angular/common";
import { Component, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { map, of, switchMap, throwError } from "rxjs";

import { AuthService } from "../../core/api/auth.service";
import { SessionService } from "../../core/auth/session.service";
import { PortalContextService } from "../../core/portal/portal-context.service";

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
  tenantCode = signal("");
  loading = signal(false);
  error = signal("");
  readonly isControlPlanePortal = this.portalContextService.isControlPlanePortal();
  readonly detectedTenantCode = this.portalContextService.suggestedTenantCode();

  constructor(
    private readonly authService: AuthService,
    private readonly sessionService: SessionService,
    private readonly portalContextService: PortalContextService,
    private readonly router: Router
  ) {
    this.tenantCode.set(this.detectedTenantCode || "acme");

    if (this.sessionService.isAuthenticated()) {
      void this.router.navigate(
        this.sessionService.session()?.portalType === "CONTROL_PLANE"
          ? ["/platform/tenants"]
          : ["/sales/flow"]
      );
    }
  }

  login(): void {
    this.loading.set(true);
    this.error.set("");

    const username = this.username().trim();
    const password = this.password();
    const inputTenantCode = this.tenantCode().trim().toLowerCase();

    if (!username || !password) {
      this.error.set("Preencha username e password.");
      this.loading.set(false);
      return;
    }
    if (!this.isControlPlanePortal && !inputTenantCode && !this.detectedTenantCode) {
      this.error.set("Tenant code obrigatório para o portal do tenant.");
      this.loading.set(false);
      return;
    }

    this.authService
      .obtainToken(username, password)
      .pipe(
        switchMap((tokenResponse) =>
          this.authService.getAuthenticatedUser(tokenResponse.token).pipe(
            map((authenticatedUser) => ({
              token: tokenResponse.token,
              authenticatedUser,
            }))
          )
        ),
        switchMap(({ token, authenticatedUser }) => {
          const resolvedTenantCode = this.resolveTenantCode(
            inputTenantCode,
            authenticatedUser.memberships.map((membership) => membership.tenant_code)
          );

          if (this.isControlPlanePortal) {
            if (!authenticatedUser.platform_admin) {
              return throwError(
                () => new Error("Usuário sem permissão para o portal Control Plane.")
              );
            }
            if (!resolvedTenantCode) {
              return of({
                token,
                authenticatedUser,
                tenantMe: null,
                resolvedTenantCode: null,
              });
            }
            return this.authService.getTenantMe(resolvedTenantCode, token).pipe(
              map((tenantMe) => ({
                token,
                authenticatedUser,
                tenantMe,
                resolvedTenantCode,
              }))
            );
          }

          if (!resolvedTenantCode) {
            return throwError(
              () => new Error("Tenant code não identificado para o portal do tenant.")
            );
          }
          return this.authService.getTenantMe(resolvedTenantCode, token).pipe(
            map((tenantMe) => ({
              token,
              authenticatedUser,
              tenantMe,
              resolvedTenantCode,
            }))
          );
        })
      )
      .subscribe({
        next: ({ token, tenantMe, authenticatedUser, resolvedTenantCode }) => {
          const fallbackRole =
            authenticatedUser.memberships.find(
              (membership) => membership.tenant_code === resolvedTenantCode
            )?.role ?? null;

          this.sessionService.saveSession({
            token,
            tenantCode: tenantMe?.tenant_code ?? resolvedTenantCode,
            username: authenticatedUser.username,
            role: tenantMe?.role ?? fallbackRole,
            platformAdmin: authenticatedUser.platform_admin,
            portalType: this.isControlPlanePortal ? "CONTROL_PLANE" : "TENANT",
          });
          this.loading.set(false);
          void this.router.navigate(
            this.isControlPlanePortal ? ["/platform/tenants"] : ["/sales/flow"]
          );
        },
        error: (err) => {
          const errorMessage =
            err instanceof Error
              ? err.message
              : err?.error?.detail
                ? JSON.stringify(err.error.detail)
                : "Falha de autenticação.";
          this.error.set(errorMessage);
          this.loading.set(false);
        },
      });
  }

  private resolveTenantCode(
    inputTenantCode: string,
    membershipTenantCodes: string[]
  ): string {
    if (inputTenantCode) {
      return inputTenantCode;
    }
    if (this.detectedTenantCode) {
      return this.detectedTenantCode;
    }
    if (membershipTenantCodes.length === 1) {
      return membershipTenantCodes[0];
    }
    return "";
  }
}
