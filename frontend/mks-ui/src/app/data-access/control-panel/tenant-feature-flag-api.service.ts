import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import {
  FeatureFlagDto,
  PaginatedResponseDto,
  TenantFeatureFlagDto,
  TenantFeatureFlagUpdateDto,
} from "./control-panel.dto";

@Injectable({ providedIn: "root" })
export class TenantFeatureFlagApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly tenantsUrl = buildApiUrl(this.config, "/api/control-panel/tenants/");
  private readonly featuresUrl = buildApiUrl(this.config, "/api/control-panel/features/");

  listGlobalFeatureFlags(): Observable<FeatureFlagDto[] | PaginatedResponseDto<FeatureFlagDto>> {
    return this.http.get<FeatureFlagDto[] | PaginatedResponseDto<FeatureFlagDto>>(this.featuresUrl);
  }

  listTenantFeatureFlags(
    tenantId: number
  ): Observable<TenantFeatureFlagDto[] | PaginatedResponseDto<TenantFeatureFlagDto>> {
    return this.http.get<TenantFeatureFlagDto[] | PaginatedResponseDto<TenantFeatureFlagDto>>(
      `${this.tenantsUrl}${tenantId}/features/`
    );
  }

  updateTenantFeatureFlag(
    tenantId: number,
    payload: TenantFeatureFlagUpdateDto
  ): Observable<TenantFeatureFlagDto> {
    return this.http.post<TenantFeatureFlagDto>(`${this.tenantsUrl}${tenantId}/features/`, payload);
  }
}
