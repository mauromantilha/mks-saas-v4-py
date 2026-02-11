import { HttpClient, HttpHeaders } from "@angular/common/http";
import { inject, Injectable, signal } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../config/api-config";
import { SessionService } from "../auth/session.service";
import {
  AuthenticatedUserResponse,
  PasswordResetConfirmResponse,
  PasswordResetRequestResponse,
  TenantCapabilitiesResponse,
  TenantMeResponse,
  TokenResponse,
} from "./auth.types";

@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly config = inject(API_CONFIG);
  private readonly sessionService = inject(SessionService);

  private readonly tokenUrl = buildApiUrl(this.config, "/api/auth/token/");
  private readonly tenantMeUrl = buildApiUrl(this.config, "/api/auth/tenant-me/");
  private readonly capabilitiesUrl = buildApiUrl(this.config, "/api/auth/capabilities/");
  private readonly meUrl = buildApiUrl(this.config, "/api/auth/me/");
  private readonly passwordResetRequestUrl = buildApiUrl(
    this.config,
    "/api/auth/password-reset/request/"
  );
  private readonly passwordResetConfirmUrl = buildApiUrl(
    this.config,
    "/api/auth/password-reset/confirm/"
  );
  private readonly accessTokenState = signal<string | null>(
    this.sessionService.session()?.token ?? null
  );

  constructor(private readonly http: HttpClient) {}

  getAccessToken(): string | null {
    const sessionToken = this.sessionService.session()?.token ?? null;
    if (sessionToken !== this.accessTokenState()) {
      this.accessTokenState.set(sessionToken);
    }
    return this.accessTokenState();
  }

  setAccessToken(token: string | null): void {
    this.accessTokenState.set(token);
  }

  clearAccessToken(): void {
    this.accessTokenState.set(null);
  }

  obtainToken(username: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(this.tokenUrl, {
      username,
      password,
    });
  }

  getTenantMe(tenantCode: string, token: string): Observable<TenantMeResponse> {
    return this.http.get<TenantMeResponse>(this.tenantMeUrl, {
      headers: this.buildHeaders(tenantCode, token),
    });
  }

  getTenantCapabilities(): Observable<TenantCapabilitiesResponse> {
    return this.http.get<TenantCapabilitiesResponse>(this.capabilitiesUrl);
  }

  getAuthenticatedUser(token: string): Observable<AuthenticatedUserResponse> {
    return this.http.get<AuthenticatedUserResponse>(this.meUrl, {
      headers: new HttpHeaders({
        Authorization: `Token ${token}`,
      }),
    });
  }

  requestPasswordReset(payload: {
    email?: string;
    username?: string;
  }): Observable<PasswordResetRequestResponse> {
    return this.http.post<PasswordResetRequestResponse>(
      this.passwordResetRequestUrl,
      payload
    );
  }

  confirmPasswordReset(payload: {
    uid: string;
    token: string;
    new_password: string;
    new_password_confirm: string;
  }): Observable<PasswordResetConfirmResponse> {
    return this.http.post<PasswordResetConfirmResponse>(
      this.passwordResetConfirmUrl,
      payload
    );
  }

  private buildHeaders(tenantCode: string, token: string): HttpHeaders {
    return new HttpHeaders({
      Authorization: `Token ${token}`,
      [this.config.tenantIdHeader]: tenantCode,
    });
  }
}
