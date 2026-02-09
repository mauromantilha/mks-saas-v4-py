import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  CreateInsurerPayload,
  InsurerRecord,
  InsurerStatus,
  UpdateInsurerPayload,
} from "./insurance-core.types";

@Injectable({ providedIn: "root" })
export class InsuranceCoreService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/insurance`
    : "/api/insurance";

  constructor(private readonly http: HttpClient) {}

  listInsurers(filters?: {
    q?: string;
    status?: InsurerStatus | "";
  }): Observable<InsurerRecord[]> {
    let params = new HttpParams();
    if (filters?.q?.trim()) {
      params = params.set("q", filters.q.trim());
    }
    if (filters?.status?.trim()) {
      params = params.set("status", filters.status.trim());
    }
    return this.http.get<InsurerRecord[]>(`${this.apiBase}/insurers/`, { params });
  }

  createInsurer(payload: CreateInsurerPayload): Observable<InsurerRecord> {
    return this.http.post<InsurerRecord>(`${this.apiBase}/insurers/`, payload);
  }

  updateInsurer(id: number, payload: UpdateInsurerPayload): Observable<InsurerRecord> {
    return this.http.patch<InsurerRecord>(`${this.apiBase}/insurers/${id}/`, payload);
  }

  deactivateInsurer(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/insurers/${id}/`);
  }
}

