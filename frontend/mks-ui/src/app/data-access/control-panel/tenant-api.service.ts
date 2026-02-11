import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import {
  MonitoringAlertDto,
  PaginatedResponseDto,
  TenantCreateDto,
  TenantDeleteDto,
  TenantDto,
  TenantIntegrationSecretRefDto,
  TenantIntegrationSecretRefUpsertDto,
  TenantListParams,
  TenantListResponseDto,
  TenantOperationalSettingsDto,
  TenantOperationalSettingsUpdateDto,
  TenantReleaseRecordCreateDto,
  TenantReleaseRecordDto,
  TenantStatusChangeDto,
  TenantUpdateDto,
} from "./control-panel.dto";
import { buildHttpParams } from "./query-params.util";

@Injectable({ providedIn: "root" })
export class TenantApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly baseUrl = buildApiUrl(this.config, "/control-panel/tenants/");

  listTenants(params?: TenantListParams): Observable<TenantListResponseDto> {
    const page = params?.page ?? 1;
    const pageSize = params?.page_size ?? 10;

    return this.http
      .get<TenantDto[] | PaginatedResponseDto<TenantDto>>(this.baseUrl, {
        params: buildHttpParams({
          status: params?.status,
          plan: params?.plan,
          trial: params?.trial === "" ? undefined : params?.trial,
          search: params?.search,
          page,
          page_size: pageSize,
        }),
      })
      .pipe(
        map((response) => {
          if (Array.isArray(response)) {
            return {
              items: response,
              total: response.length,
              page,
              page_size: pageSize,
            };
          }

          return {
            items: response.results ?? [],
            total: response.count ?? 0,
            page,
            page_size: pageSize,
          };
        })
      );
  }

  getTenant(id: number): Observable<TenantDto> {
    return this.http.get<TenantDto>(`${this.baseUrl}${id}/`);
  }

  createTenant(dto: TenantCreateDto): Observable<TenantDto> {
    return this.http.post<TenantDto>(this.baseUrl, dto);
  }

  updateTenant(id: number, dto: TenantUpdateDto): Observable<TenantDto> {
    return this.http.patch<TenantDto>(`${this.baseUrl}${id}/`, dto);
  }

  suspendTenant(id: number, payload: TenantStatusChangeDto = {}): Observable<TenantDto> {
    return this.http.post<TenantDto>(`${this.baseUrl}${id}/suspend/`, payload);
  }

  unsuspendTenant(id: number, payload: TenantStatusChangeDto = {}): Observable<TenantDto> {
    return this.http.post<TenantDto>(`${this.baseUrl}${id}/unsuspend/`, payload);
  }

  deleteTenant(id: number, payload: TenantDeleteDto): Observable<TenantDto> {
    return this.http.post<TenantDto>(`${this.baseUrl}${id}/delete/`, payload);
  }

  exportTenantData(id: number): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(`${this.baseUrl}${id}/export/`, {});
  }

  getTenantLimits(id: number): Observable<TenantOperationalSettingsDto> {
    return this.http.get<TenantOperationalSettingsDto>(`${this.baseUrl}${id}/limits/`);
  }

  updateTenantLimits(
    id: number,
    payload: TenantOperationalSettingsUpdateDto
  ): Observable<TenantOperationalSettingsDto> {
    return this.http.post<TenantOperationalSettingsDto>(`${this.baseUrl}${id}/limits/`, payload);
  }

  listTenantIntegrations(
    id: number
  ): Observable<TenantIntegrationSecretRefDto[] | PaginatedResponseDto<TenantIntegrationSecretRefDto>> {
    return this.http.get<TenantIntegrationSecretRefDto[] | PaginatedResponseDto<TenantIntegrationSecretRefDto>>(
      `${this.baseUrl}${id}/integrations/`
    );
  }

  upsertTenantIntegration(
    id: number,
    payload: TenantIntegrationSecretRefUpsertDto
  ): Observable<TenantIntegrationSecretRefDto> {
    return this.http.post<TenantIntegrationSecretRefDto>(`${this.baseUrl}${id}/integrations/`, payload);
  }

  listTenantChangelog(
    id: number
  ): Observable<TenantReleaseRecordDto[] | PaginatedResponseDto<TenantReleaseRecordDto>> {
    return this.http.get<TenantReleaseRecordDto[] | PaginatedResponseDto<TenantReleaseRecordDto>>(
      `${this.baseUrl}${id}/changelog/`
    );
  }

  createTenantChangelog(id: number, payload: TenantReleaseRecordCreateDto): Observable<TenantReleaseRecordDto> {
    return this.http.post<TenantReleaseRecordDto>(`${this.baseUrl}${id}/changelog/`, payload);
  }

  listTenantAlerts(
    id: number,
    status?: "OPEN" | "RESOLVED"
  ): Observable<MonitoringAlertDto[] | PaginatedResponseDto<MonitoringAlertDto>> {
    return this.http.get<MonitoringAlertDto[] | PaginatedResponseDto<MonitoringAlertDto>>(
      `${this.baseUrl}${id}/alerts/`,
      {
        params: buildHttpParams({
          status: status || undefined,
        }),
      }
    );
  }

  resolveTenantAlert(id: number, alertId: number): Observable<MonitoringAlertDto> {
    return this.http.post<MonitoringAlertDto>(`${this.baseUrl}${id}/alerts/resolve/`, { alert_id: alertId });
  }

  startTenantImpersonation(
    id: number,
    payload: { reason?: string; duration_minutes?: number }
  ): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(`${this.baseUrl}${id}/impersonate/`, payload);
  }

  stopTenantImpersonation(
    id: number,
    payload: { session_id?: number } = {}
  ): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(`${this.baseUrl}${id}/impersonate/stop/`, payload);
  }
}
