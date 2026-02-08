import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  AuthenticatedUserResponse,
  TenantCapabilitiesResponse,
  TenantMeResponse,
  TokenResponse,
} from "./auth.types";

@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly tokenUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/token/`
    : "/api/auth/token/";
  private readonly tenantMeUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-me/`
    : "/api/auth/tenant-me/";
  private readonly capabilitiesUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/capabilities/`
    : "/api/auth/capabilities/";
  private readonly meUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/me/`
    : "/api/auth/me/";

  constructor(private readonly http: HttpClient) {}

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

  private buildHeaders(tenantCode: string, token: string): HttpHeaders {
    return new HttpHeaders({
      Authorization: `Token ${token}`,
      [environment.tenantIdHeader]: tenantCode,
    });
  }
}
