import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import {
  GlobalMonitoringDto,
  GlobalMonitoringParams,
  MonitoringAlertDto,
  TenantMonitoringDto,
  TenantMonitoringParams,
} from "./control-panel.dto";
import { buildHttpParams } from "./query-params.util";

@Injectable({ providedIn: "root" })
export class MonitoringApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly monitoringUrl = buildApiUrl(this.config, "/control-panel/monitoring/");
  private readonly tenantsUrl = buildApiUrl(this.config, "/control-panel/tenants/");

  getGlobalHealth(params?: GlobalMonitoringParams): Observable<GlobalMonitoringDto> {
    return this.http.get<GlobalMonitoringDto>(this.monitoringUrl, {
      params: buildHttpParams({
        period: params?.period,
        page: params?.page,
        page_size: params?.page_size,
      }),
    });
  }

  getTenantHealth(
    tenantId: number,
    params?: TenantMonitoringParams
  ): Observable<TenantMonitoringDto> {
    return this.http.get<TenantMonitoringDto>(`${this.tenantsUrl}${tenantId}/monitoring/`, {
      params: buildHttpParams({
        period: params?.period,
        page: params?.page,
        page_size: params?.page_size,
      }),
    });
  }

  acknowledgeAlert(alertId: number): Observable<MonitoringAlertDto> {
    return this.http.post<MonitoringAlertDto>(`${this.monitoringUrl}alerts/${alertId}/ack/`, {});
  }
}
