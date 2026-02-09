import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  CreateSalesGoalPayload,
  SalesGoalRecord,
  TenantDashboardSummary,
  UpdateSalesGoalPayload,
} from "./tenant-dashboard.types";

@Injectable({ providedIn: "root" })
export class TenantDashboardService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";

  constructor(private readonly http: HttpClient) {}

  getSummary(): Observable<TenantDashboardSummary> {
    return this.http.get<TenantDashboardSummary>(`${this.apiBase}/dashboard/summary/`);
  }

  listSalesGoals(): Observable<SalesGoalRecord[]> {
    return this.http.get<SalesGoalRecord[]>(`${this.apiBase}/sales-goals/`);
  }

  createSalesGoal(payload: CreateSalesGoalPayload): Observable<SalesGoalRecord> {
    return this.http.post<SalesGoalRecord>(`${this.apiBase}/sales-goals/`, payload);
  }

  updateSalesGoal(id: number, payload: UpdateSalesGoalPayload): Observable<SalesGoalRecord> {
    return this.http.patch<SalesGoalRecord>(`${this.apiBase}/sales-goals/${id}/`, payload);
  }
}
