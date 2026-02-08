import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  CommercialActivityRecord,
  CreateCommercialActivityPayload,
  LeadRecord,
  LeadHistoryRecord,
  OpportunityRecord,
  OpportunityHistoryRecord,
  OpportunityStage,
  SalesMetricsRecord,
} from "./sales-flow.types";

@Injectable({ providedIn: "root" })
export class SalesFlowService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";

  constructor(private readonly http: HttpClient) {}

  listLeads(): Observable<LeadRecord[]> {
    return this.http.get<LeadRecord[]>(`${this.apiBase}/leads/`);
  }

  listOpportunities(): Observable<OpportunityRecord[]> {
    return this.http.get<OpportunityRecord[]>(`${this.apiBase}/opportunities/`);
  }

  listActivities(): Observable<CommercialActivityRecord[]> {
    return this.http.get<CommercialActivityRecord[]>(`${this.apiBase}/activities/`);
  }

  listReminderActivities(): Observable<CommercialActivityRecord[]> {
    return this.http.get<CommercialActivityRecord[]>(
      `${this.apiBase}/activities/reminders/`
    );
  }

  createActivity(
    payload: CreateCommercialActivityPayload
  ): Observable<CommercialActivityRecord> {
    return this.http.post<CommercialActivityRecord>(
      `${this.apiBase}/activities/`,
      payload
    );
  }

  completeActivity(id: number): Observable<CommercialActivityRecord> {
    return this.http.post<CommercialActivityRecord>(
      `${this.apiBase}/activities/${id}/complete/`,
      {}
    );
  }

  reopenActivity(id: number): Observable<CommercialActivityRecord> {
    return this.http.post<CommercialActivityRecord>(
      `${this.apiBase}/activities/${id}/reopen/`,
      {}
    );
  }

  markActivityReminded(id: number): Observable<CommercialActivityRecord> {
    return this.http.post<CommercialActivityRecord>(
      `${this.apiBase}/activities/${id}/mark-reminded/`,
      {}
    );
  }

  getLeadHistory(id: number): Observable<LeadHistoryRecord> {
    return this.http.get<LeadHistoryRecord>(`${this.apiBase}/leads/${id}/history/`);
  }

  getOpportunityHistory(id: number): Observable<OpportunityHistoryRecord> {
    return this.http.get<OpportunityHistoryRecord>(
      `${this.apiBase}/opportunities/${id}/history/`
    );
  }

  getSalesMetrics(): Observable<SalesMetricsRecord> {
    return this.http.get<SalesMetricsRecord>(`${this.apiBase}/sales/metrics/`);
  }

  qualifyLead(id: number): Observable<LeadRecord> {
    return this.http.post<LeadRecord>(`${this.apiBase}/leads/${id}/qualify/`, {});
  }

  disqualifyLead(id: number): Observable<LeadRecord> {
    return this.http.post<LeadRecord>(`${this.apiBase}/leads/${id}/disqualify/`, {});
  }

  convertLead(id: number): Observable<unknown> {
    return this.http.post(`${this.apiBase}/leads/${id}/convert/`, {});
  }

  updateOpportunityStage(
    id: number,
    stage: OpportunityStage
  ): Observable<OpportunityRecord> {
    return this.http.post<OpportunityRecord>(
      `${this.apiBase}/opportunities/${id}/stage/`,
      { stage }
    );
  }
}
