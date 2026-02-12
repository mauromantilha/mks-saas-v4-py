import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  BankCatalogResponse,
  TenantMember,
  TenantMemberPatchPayload,
  TenantMemberUpsertPayload,
  TenantMembersListResponse,
  TenantProducer,
  TenantProducerPatchPayload,
  TenantProducerPerformanceResponse,
  TenantProducersListResponse,
  TenantProducerUpsertPayload,
} from "./tenant-members.types";

@Injectable({ providedIn: "root" })
export class TenantMembersService {
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-members/`
    : "/api/auth/tenant-members/";
  private readonly producersUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-producers/`
    : "/api/auth/tenant-producers/";
  private readonly producerPerformanceUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-producers/performance/`
    : "/api/auth/tenant-producers/performance/";
  private readonly banksUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/utils/banks/`
    : "/api/utils/banks/";

  constructor(private readonly http: HttpClient) {}

  list(): Observable<TenantMembersListResponse> {
    return this.http.get<TenantMembersListResponse>(this.baseUrl);
  }

  upsert(payload: TenantMemberUpsertPayload): Observable<TenantMember> {
    return this.http.post<TenantMember>(this.baseUrl, payload);
  }

  patch(id: number, payload: TenantMemberPatchPayload): Observable<TenantMember> {
    return this.http.patch<TenantMember>(`${this.baseUrl}${id}/`, payload);
  }

  deactivate(id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}${id}/`);
  }

  listProducers(): Observable<TenantProducersListResponse> {
    return this.http.get<TenantProducersListResponse>(this.producersUrl);
  }

  upsertProducer(payload: TenantProducerUpsertPayload): Observable<TenantProducer> {
    return this.http.post<TenantProducer>(this.producersUrl, payload);
  }

  patchProducer(id: number, payload: TenantProducerPatchPayload): Observable<TenantProducer> {
    return this.http.patch<TenantProducer>(`${this.producersUrl}${id}/`, payload);
  }

  getProducerPerformance(): Observable<TenantProducerPerformanceResponse> {
    return this.http.get<TenantProducerPerformanceResponse>(this.producerPerformanceUrl);
  }

  listBanks(): Observable<BankCatalogResponse> {
    return this.http.get<BankCatalogResponse>(this.banksUrl);
  }
}
