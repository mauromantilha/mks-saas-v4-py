import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  TenantMember,
  TenantMemberPatchPayload,
  TenantMemberUpsertPayload,
  TenantMembersListResponse,
} from "./tenant-members.types";

@Injectable({ providedIn: "root" })
export class TenantMembersService {
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/auth/tenant-members/`
    : "/api/auth/tenant-members/";

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
}
