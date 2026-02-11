import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, Observable } from "rxjs";

import { API_CONFIG, buildApiUrl } from "../../core/config/api-config";
import {
  PaginatedResponseDto,
  TenantCreateDto,
  TenantDeleteDto,
  TenantDto,
  TenantListParams,
  TenantListResponseDto,
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
}
