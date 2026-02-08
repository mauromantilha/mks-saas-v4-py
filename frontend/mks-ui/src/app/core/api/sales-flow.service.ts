import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  LeadRecord,
  OpportunityRecord,
  OpportunityStage,
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
