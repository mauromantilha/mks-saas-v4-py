import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";

import {
  TenantRbacOverrides,
  TenantRbacResponse,
} from "./tenant-rbac.types";
import { environment } from "../../../environments/environment";

@Injectable({ providedIn: "root" })
export class TenantRbacService {
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-rbac/`
    : "/api/auth/tenant-rbac/";

  constructor(private readonly http: HttpClient) {}

  getTenantRbac(): Observable<TenantRbacResponse> {
    return this.http.get<TenantRbacResponse>(this.baseUrl);
  }

  replaceTenantRbac(overrides: TenantRbacOverrides): Observable<TenantRbacResponse> {
    return this.http.put<TenantRbacResponse>(
      this.baseUrl,
      { rbac_overrides: overrides }
    );
  }

  patchTenantRbac(partialOverrides: TenantRbacOverrides): Observable<TenantRbacResponse> {
    return this.http.patch<TenantRbacResponse>(
      this.baseUrl,
      { rbac_overrides: partialOverrides }
    );
  }
}
