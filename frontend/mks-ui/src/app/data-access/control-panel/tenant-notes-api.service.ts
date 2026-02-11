import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import {
  PaginatedResponseDto,
  TenantInternalNoteCreateDto,
  TenantInternalNoteDto,
} from "./control-panel.dto";

@Injectable({ providedIn: "root" })
export class TenantNotesApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(API_CONFIG);
  private readonly tenantsUrl = buildApiUrl(this.config, "/api/control-panel/tenants/");

  listTenantNotes(
    tenantId: number
  ): Observable<TenantInternalNoteDto[] | PaginatedResponseDto<TenantInternalNoteDto>> {
    return this.http.get<TenantInternalNoteDto[] | PaginatedResponseDto<TenantInternalNoteDto>>(
      `${this.tenantsUrl}${tenantId}/notes/`
    );
  }

  createTenantNote(tenantId: number, payload: TenantInternalNoteCreateDto): Observable<TenantInternalNoteDto> {
    return this.http.post<TenantInternalNoteDto>(`${this.tenantsUrl}${tenantId}/notes/`, payload);
  }
}
