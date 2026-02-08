import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  CreatePlatformTenantPayload,
  PlatformTenantRecord,
  ProvisionTenantPayload,
} from "./platform-tenants.types";

@Injectable({ providedIn: "root" })
export class PlatformTenantsService {
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/platform/api/tenants/`
    : "/platform/api/tenants/";

  constructor(private readonly http: HttpClient) {}

  listTenants(search?: string): Observable<PlatformTenantRecord[]> {
    if (!search?.trim()) {
      return this.http.get<PlatformTenantRecord[]>(this.baseUrl);
    }
    return this.http.get<PlatformTenantRecord[]>(
      `${this.baseUrl}?q=${encodeURIComponent(search.trim())}`
    );
  }

  createTenant(payload: CreatePlatformTenantPayload): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(this.baseUrl, payload);
  }

  patchTenant(
    companyId: number,
    payload: Record<string, unknown>
  ): Observable<PlatformTenantRecord> {
    return this.http.patch<PlatformTenantRecord>(`${this.baseUrl}${companyId}/`, payload);
  }

  provisionTenant(
    companyId: number,
    payload: ProvisionTenantPayload
  ): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(
      `${this.baseUrl}${companyId}/provision/`,
      payload
    );
  }
}
