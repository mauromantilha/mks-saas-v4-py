import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";
import { map } from "rxjs/operators";

import { environment } from "../../../environments/environment";

export type SalesFlowOrigin = "LEAD" | "OPPORTUNITY" | "PROJECT" | "CUSTOMER";
export type SalesFlowActivityType = "TASK" | "FOLLOW_UP" | "NOTE" | "MEETING";
export type SalesFlowActivityPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface SalesFlowSummaryResponse {
  leads_new: number;
  leads_qualified: number;
  leads_converted: number;
  opportunities_won: number;
  winrate: number;
  pipeline_open: number;
  activities_open: number;
  activities_overdue: number;
}

export interface AgendaEventRecord {
  id: number;
  title: string;
  subject: string;
  status: string;
  priority: SalesFlowActivityPriority;
  origin: SalesFlowOrigin;
  start_at: string | null;
  end_at: string | null;
  remind_at: string | null;
  attendee_name: string;
  attendee_email: string;
  invite_sent_at: string | null;
  confirmed_at: string | null;
  canceled_at: string | null;
  reminder_state: "PENDING" | "SENT" | "ACKED";
  lead: number | null;
  opportunity: number | null;
  project: number | null;
  customer: number | null;
  created_at: string;
  updated_at: string;
}

interface AgendaListResponse {
  tenant_code: string;
  results: AgendaEventRecord[];
}

export interface CreateSalesActivityPayload {
  kind: SalesFlowActivityType;
  title: string;
  description?: string;
  priority?: SalesFlowActivityPriority;
  due_at?: string | null;
  reminder_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  lead?: number | null;
  opportunity?: number | null;
}

export interface CreateAgendaPayload {
  title: string;
  subject?: string;
  start_at: string;
  end_at?: string | null;
  attendee_name?: string;
  attendee_email?: string;
  send_invite?: boolean;
  priority?: SalesFlowActivityPriority;
  lead?: number | null;
  opportunity?: number | null;
  project?: number | null;
  customer?: number | null;
}

@Injectable({ providedIn: "root" })
export class TenantSalesFlowService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";

  constructor(private readonly http: HttpClient) {}

  getSummary(): Observable<SalesFlowSummaryResponse> {
    return this.http.get<SalesFlowSummaryResponse>(`${this.apiBase}/sales-flow/summary/`);
  }

  createActivity(payload: CreateSalesActivityPayload): Observable<unknown> {
    return this.http.post(`${this.apiBase}/activities/`, payload);
  }

  listAgenda(filters?: {
    date_from?: string;
    date_to?: string;
  }): Observable<AgendaEventRecord[]> {
    let params = new HttpParams();
    if (filters?.date_from?.trim()) {
      params = params.set("date_from", filters.date_from.trim());
    }
    if (filters?.date_to?.trim()) {
      params = params.set("date_to", filters.date_to.trim());
    }

    return this.http
      .get<AgendaListResponse>(`${this.apiBase}/agenda/`, { params })
      .pipe(map((response) => response?.results || []));
  }

  createAgenda(payload: CreateAgendaPayload): Observable<AgendaEventRecord> {
    return this.http.post<AgendaEventRecord>(`${this.apiBase}/agenda/`, payload);
  }

  listAgendaReminders(): Observable<AgendaEventRecord[]> {
    return this.http
      .get<AgendaListResponse>(`${this.apiBase}/agenda/reminders/`)
      .pipe(map((response) => response?.results || []));
  }

  confirmAgenda(agendaId: number, send_email = false): Observable<AgendaEventRecord> {
    return this.http.post<AgendaEventRecord>(
      `${this.apiBase}/agenda/${agendaId}/confirm/`,
      { send_email }
    );
  }

  cancelAgenda(agendaId: number): Observable<AgendaEventRecord> {
    return this.http.post<AgendaEventRecord>(`${this.apiBase}/agenda/${agendaId}/cancel/`, {});
  }

  ackAgendaReminder(agendaId: number): Observable<AgendaEventRecord> {
    return this.http.post<AgendaEventRecord>(
      `${this.apiBase}/agenda/${agendaId}/ack-reminder/`,
      {}
    );
  }
}
