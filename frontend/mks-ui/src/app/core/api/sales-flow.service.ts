import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  AIInsightResponse,
  AIInsightsRequestPayload,
  CepLookupResponse,
  CommercialActivityRecord,
  CNPJEnrichmentResponse,
  CreatePolicyRequestPayload,
  CreateProposalOptionPayload,
  CreateSpecialProjectActivityPayload,
  CreateSpecialProjectPayload,
  CreateCustomerPayload,
  CreateCommercialActivityPayload,
  CreateLeadPayload,
  CreateOpportunityPayload,
  CustomerRecord,
  UpdateCustomerPayload,
  LeadConvertPayload,
  LeadConvertResponse,
  LeadRecord,
  LeadHistoryRecord,
  PolicyRequestRecord,
  OpportunityRecord,
  OpportunityHistoryRecord,
  OpportunityStage,
  UpdatePolicyRequestPayload,
  UpdateLeadPayload,
  ProposalOptionRecord,
  SpecialProjectActivityRecord,
  SpecialProjectDocumentRecord,
  SpecialProjectRecord,
  UpdateSpecialProjectPayload,
  UpdateProposalOptionPayload,
  SalesMetricsFilters,
  SalesMetricsRecord,
  TenantAIAssistantConsultRequest,
  TenantAIAssistantConsultResponse,
  TenantAIAssistantListResponse,
} from "./sales-flow.types";

@Injectable({ providedIn: "root" })
export class SalesFlowService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";

  constructor(private readonly http: HttpClient) {}

  listCustomers(): Observable<CustomerRecord[]> {
    return this.http.get<CustomerRecord[]>(`${this.apiBase}/customers/`);
  }

  createCustomer(payload: CreateCustomerPayload): Observable<CustomerRecord> {
    return this.http.post<CustomerRecord>(`${this.apiBase}/customers/`, payload);
  }

  getCustomer(id: number): Observable<CustomerRecord> {
    return this.http.get<CustomerRecord>(`${this.apiBase}/customers/${id}/`);
  }

  updateCustomer(id: number, payload: UpdateCustomerPayload): Observable<CustomerRecord> {
    return this.http.patch<CustomerRecord>(`${this.apiBase}/customers/${id}/`, payload);
  }

  deleteCustomer(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/customers/${id}/`);
  }

  lookupCep(cep: string): Observable<CepLookupResponse> {
    const encoded = encodeURIComponent((cep || "").trim());
    return this.http.get<CepLookupResponse>(`${this.apiBase}/utils/cep/${encoded}/`);
  }

  listLeads(): Observable<LeadRecord[]> {
    return this.http.get<LeadRecord[]>(`${this.apiBase}/leads/`);
  }

  createLead(payload: CreateLeadPayload): Observable<LeadRecord> {
    return this.http.post<LeadRecord>(`${this.apiBase}/leads/`, payload);
  }

  updateLead(id: number, payload: UpdateLeadPayload): Observable<LeadRecord> {
    return this.http.patch<LeadRecord>(`${this.apiBase}/leads/${id}/`, payload);
  }

  listOpportunities(): Observable<OpportunityRecord[]> {
    return this.http.get<OpportunityRecord[]>(`${this.apiBase}/opportunities/`);
  }

  createOpportunity(payload: CreateOpportunityPayload): Observable<OpportunityRecord> {
    return this.http.post<OpportunityRecord>(`${this.apiBase}/opportunities/`, payload);
  }

  listPolicyRequests(): Observable<PolicyRequestRecord[]> {
    return this.http.get<PolicyRequestRecord[]>(`${this.apiBase}/policy-requests/`);
  }

  createPolicyRequest(
    payload: CreatePolicyRequestPayload
  ): Observable<PolicyRequestRecord> {
    return this.http.post<PolicyRequestRecord>(`${this.apiBase}/policy-requests/`, payload);
  }

  updatePolicyRequest(
    id: number,
    payload: UpdatePolicyRequestPayload
  ): Observable<PolicyRequestRecord> {
    return this.http.patch<PolicyRequestRecord>(
      `${this.apiBase}/policy-requests/${id}/`,
      payload
    );
  }

  listProposalOptions(): Observable<ProposalOptionRecord[]> {
    return this.http.get<ProposalOptionRecord[]>(`${this.apiBase}/proposal-options/`);
  }

  createProposalOption(
    payload: CreateProposalOptionPayload
  ): Observable<ProposalOptionRecord> {
    return this.http.post<ProposalOptionRecord>(`${this.apiBase}/proposal-options/`, payload);
  }

  updateProposalOption(
    id: number,
    payload: UpdateProposalOptionPayload
  ): Observable<ProposalOptionRecord> {
    return this.http.patch<ProposalOptionRecord>(
      `${this.apiBase}/proposal-options/${id}/`,
      payload
    );
  }

  listSpecialProjects(params?: {
    status?: string;
    project_type?: string;
    search?: string;
  }): Observable<SpecialProjectRecord[]> {
    let httpParams = new HttpParams();
    if (params?.status?.trim()) {
      httpParams = httpParams.set("status", params.status.trim());
    }
    if (params?.project_type?.trim()) {
      httpParams = httpParams.set("project_type", params.project_type.trim());
    }
    if (params?.search?.trim()) {
      httpParams = httpParams.set("search", params.search.trim());
    }
    return this.http.get<SpecialProjectRecord[]>(`${this.apiBase}/special-projects/`, {
      params: httpParams,
    });
  }

  getSpecialProject(id: number): Observable<SpecialProjectRecord> {
    return this.http.get<SpecialProjectRecord>(`${this.apiBase}/special-projects/${id}/`);
  }

  createSpecialProject(payload: CreateSpecialProjectPayload): Observable<SpecialProjectRecord> {
    return this.http.post<SpecialProjectRecord>(`${this.apiBase}/special-projects/`, payload);
  }

  updateSpecialProject(
    id: number,
    payload: UpdateSpecialProjectPayload
  ): Observable<SpecialProjectRecord> {
    return this.http.patch<SpecialProjectRecord>(
      `${this.apiBase}/special-projects/${id}/`,
      payload
    );
  }

  deleteSpecialProject(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/special-projects/${id}/`);
  }

  addSpecialProjectActivity(
    projectId: number,
    payload: CreateSpecialProjectActivityPayload
  ): Observable<SpecialProjectActivityRecord> {
    return this.http.post<SpecialProjectActivityRecord>(
      `${this.apiBase}/special-projects/${projectId}/activities/`,
      payload
    );
  }

  updateSpecialProjectActivity(
    projectId: number,
    activityId: number,
    payload: Partial<CreateSpecialProjectActivityPayload> & { status?: "OPEN" | "DONE" }
  ): Observable<SpecialProjectActivityRecord> {
    return this.http.patch<SpecialProjectActivityRecord>(
      `${this.apiBase}/special-projects/${projectId}/activities/${activityId}/`,
      payload
    );
  }

  deleteSpecialProjectActivity(projectId: number, activityId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiBase}/special-projects/${projectId}/activities/${activityId}/`
    );
  }

  uploadSpecialProjectDocument(
    projectId: number,
    file: File,
    title: string,
    notes = ""
  ): Observable<SpecialProjectDocumentRecord> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title || file.name);
    formData.append("notes", notes);
    return this.http.post<SpecialProjectDocumentRecord>(
      `${this.apiBase}/special-projects/${projectId}/documents/`,
      formData
    );
  }

  deleteSpecialProjectDocument(projectId: number, documentId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiBase}/special-projects/${projectId}/documents/${documentId}/`
    );
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

  generateActivityAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/activities/${id}/ai-insights/`,
      payload
    );
  }

  generatePolicyRequestAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/policy-requests/${id}/ai-insights/`,
      payload
    );
  }

  generateProposalOptionAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/proposal-options/${id}/ai-insights/`,
      payload
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

  getSalesMetrics(filters?: SalesMetricsFilters): Observable<SalesMetricsRecord> {
    let params = new HttpParams();
    if (filters?.from?.trim()) {
      params = params.set("from", filters.from.trim());
    }
    if (filters?.to?.trim()) {
      params = params.set("to", filters.to.trim());
    }
    if (filters?.assigned_to?.trim()) {
      params = params.set("assigned_to", filters.assigned_to.trim());
    }
    return this.http.get<SalesMetricsRecord>(`${this.apiBase}/sales/metrics/`, { params });
  }

  qualifyLead(id: number): Observable<LeadRecord> {
    return this.http.post<LeadRecord>(`${this.apiBase}/leads/${id}/qualify/`, {});
  }

  disqualifyLead(id: number): Observable<LeadRecord> {
    return this.http.post<LeadRecord>(`${this.apiBase}/leads/${id}/disqualify/`, {});
  }

  convertLead(
    id: number,
    payload: LeadConvertPayload = { create_customer_if_missing: true }
  ): Observable<LeadConvertResponse> {
    return this.http.post<LeadConvertResponse>(
      `${this.apiBase}/leads/${id}/convert/`,
      payload
    );
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

  generateLeadAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/leads/${id}/ai-insights/`,
      payload
    );
  }

  enrichLeadCnpj(
    id: number,
    cnpj?: string
  ): Observable<CNPJEnrichmentResponse> {
    return this.http.post<CNPJEnrichmentResponse>(
      `${this.apiBase}/leads/${id}/ai-enrich-cnpj/`,
      cnpj ? { cnpj } : {}
    );
  }

  generateCustomerAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/customers/${id}/ai-insights/`,
      payload
    );
  }

  enrichCustomerCnpj(
    id: number,
    cnpj?: string
  ): Observable<CNPJEnrichmentResponse> {
    return this.http.post<CNPJEnrichmentResponse>(
      `${this.apiBase}/customers/${id}/ai-enrich-cnpj/`,
      cnpj ? { cnpj } : {}
    );
  }

  generateOpportunityAIInsights(
    id: number,
    payload: AIInsightsRequestPayload
  ): Observable<AIInsightResponse> {
    return this.http.post<AIInsightResponse>(
      `${this.apiBase}/opportunities/${id}/ai-insights/`,
      payload
    );
  }

  consultTenantAIAssistant(
    payload: TenantAIAssistantConsultRequest
  ): Observable<TenantAIAssistantConsultResponse> {
    return this.http.post<TenantAIAssistantConsultResponse>(
      `${this.apiBase}/ai-assistant/consult/`,
      payload
    );
  }

  listTenantAIAssistantInteractions(
    limit = 20
  ): Observable<TenantAIAssistantListResponse> {
    let params = new HttpParams().set("limit", String(limit));
    return this.http.get<TenantAIAssistantListResponse>(
      `${this.apiBase}/ai-assistant/consult/`,
      { params }
    );
  }
}
