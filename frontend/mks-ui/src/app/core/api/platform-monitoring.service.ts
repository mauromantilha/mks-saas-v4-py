import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  ControlPanelMonitoringResponse,
  TenantMonitoringResponse,
} from "./platform-monitoring.types";

@Injectable({ providedIn: "root" })
export class PlatformMonitoringService {
  private readonly monitoringUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/control-panel/monitoring/`
    : "/api/control-panel/monitoring/";
  private readonly tenantMonitoringBaseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/control-panel/tenants/`
    : "/api/control-panel/tenants/";

  constructor(private readonly http: HttpClient) {}

  getMonitoring(period?: string): Observable<ControlPanelMonitoringResponse> {
    if (!period) {
      return this.http.get<ControlPanelMonitoringResponse>(this.monitoringUrl);
    }
    return this.http.get<ControlPanelMonitoringResponse>(
      `${this.monitoringUrl}?period=${encodeURIComponent(period)}`
    );
  }

  getTenantMonitoring(tenantId: number, period?: string): Observable<TenantMonitoringResponse> {
    const baseUrl = `${this.tenantMonitoringBaseUrl}${tenantId}/monitoring/`;
    if (!period) {
      return this.http.get<TenantMonitoringResponse>(baseUrl);
    }
    return this.http.get<TenantMonitoringResponse>(
      `${baseUrl}?period=${encodeURIComponent(period)}`
    );
  }
}
