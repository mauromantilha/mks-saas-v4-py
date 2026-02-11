import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import { AuditEventDto, AuditListParams, PaginatedResponseDto } from "./control-panel.dto";
import { buildHttpParams } from "./query-params.util";

@Injectable({ providedIn: "root" })
export class AuditApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly tenantsUrl = buildApiUrl(this.config, "/api/control-panel/tenants/");
  // Global audit endpoint can be implemented as /api/control-panel/audit/ in backend.
  // Kept configurable here to avoid frontend coupling to a temporary route.
  private readonly globalAuditUrl = buildApiUrl(this.config, "/api/control-panel/audit/");

  listAuditEvents(
    params?: AuditListParams
  ): Observable<PaginatedResponseDto<AuditEventDto> | AuditEventDto[]> {
    return this.http.get<PaginatedResponseDto<AuditEventDto> | AuditEventDto[]>(this.globalAuditUrl, {
      params: buildHttpParams({
        page: params?.page,
        page_size: params?.page_size,
        period: params?.period,
        date_from: params?.date_from,
        date_to: params?.date_to,
        tenant_id: params?.tenant_id,
        action: params?.action,
        entity_type: params?.entity_type,
        actor: params?.actor,
        search: params?.search,
      }),
    });
  }

  listTenantAuditEvents(
    tenantId: number,
    params?: AuditListParams
  ): Observable<PaginatedResponseDto<AuditEventDto> | AuditEventDto[]> {
    return this.http.get<PaginatedResponseDto<AuditEventDto> | AuditEventDto[]>(
      `${this.tenantsUrl}${tenantId}/audit/`,
      {
      params: buildHttpParams({
        page: params?.page,
        page_size: params?.page_size,
        period: params?.period,
        date_from: params?.date_from,
        date_to: params?.date_to,
        action: params?.action,
        entity_type: params?.entity_type,
        actor: params?.actor,
        search: params?.search,
      }),
      }
    );
  }
}
