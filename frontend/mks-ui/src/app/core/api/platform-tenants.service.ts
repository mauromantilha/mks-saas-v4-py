import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  AdminAuditEventRecord,
  ContractEmailLogRecord,
  CreatePlatformTenantPayload,
  FeatureFlagRecord,
  PlanPayload,
  PlanRecord,
  PlatformTenantRecord,
  TenantContractRecord,
  TenantImpersonationSessionRecord,
  TenantIntegrationSecretRefRecord,
  TenantListFilters,
  TenantAlertEventRecord,
  TenantFeatureFlagRecord,
  TenantInternalNoteRecord,
  TenantOperationalSettingsRecord,
  TenantReleaseRecord,
  TenantSubscriptionPayload,
} from "./platform-tenants.types";

@Injectable({ providedIn: "root" })
export class PlatformTenantsService {
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/control-panel/tenants/`
    : "/control-panel/tenants/";
  private readonly plansUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/control-panel/plans/`
    : "/control-panel/plans/";
  private readonly controlPanelCepBaseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/control-panel/utils/cep/`
    : "/control-panel/utils/cep/";

  constructor(private readonly http: HttpClient) {}

  listTenants(filters?: TenantListFilters): Observable<PlatformTenantRecord[]> {
    const params = new URLSearchParams();
    if (filters?.status) {
      params.set("status", filters.status);
    }
    if (filters?.planId) {
      params.set("plan", String(filters.planId));
    }
    if (filters?.trial) {
      params.set("trial", filters.trial);
    }
    if (filters?.search?.trim()) {
      params.set("search", filters.search.trim());
    }

    const query = params.toString();
    const url = query ? `${this.baseUrl}?${query}` : this.baseUrl;
    return this.http.get<PlatformTenantRecord[]>(url);
  }

  getTenant(tenantId: number): Observable<PlatformTenantRecord> {
    return this.http.get<PlatformTenantRecord>(`${this.baseUrl}${tenantId}/`);
  }

  createTenant(payload: CreatePlatformTenantPayload): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(this.baseUrl, payload);
  }

  patchTenant(
    companyId: number,
    payload: Record<string, unknown>
  ): Observable<PlatformTenantRecord> {
    return this.http.patch<PlatformTenantRecord>(`${this.baseUrl}${companyId}/`, payload);
  }

  listPlans(): Observable<PlanRecord[]> {
    return this.http.get<PlanRecord[]>(this.plansUrl);
  }

  createPlan(payload: PlanPayload): Observable<PlanRecord> {
    return this.http.post<PlanRecord>(this.plansUrl, payload);
  }

  patchPlan(planId: number, payload: Partial<PlanPayload>): Observable<PlanRecord> {
    return this.http.patch<PlanRecord>(`${this.plansUrl}${planId}/`, payload);
  }

  changeSubscription(
    tenantId: number,
    payload: TenantSubscriptionPayload
  ): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(
      `${this.baseUrl}${tenantId}/subscription/`,
      payload
    );
  }

  suspendTenant(tenantId: number, reason: string): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(`${this.baseUrl}${tenantId}/suspend/`, {
      reason,
    });
  }

  unsuspendTenant(tenantId: number, reason: string): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(`${this.baseUrl}${tenantId}/unsuspend/`, {
      reason,
    });
  }

  softDeleteTenant(
    tenantId: number,
    reason: string,
    confirmText: string
  ): Observable<PlatformTenantRecord> {
    return this.http.post<PlatformTenantRecord>(`${this.baseUrl}${tenantId}/delete/`, {
      reason,
      confirm_text: confirmText,
    });
  }

  exportTenantData(tenantId: number): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(
      `${this.baseUrl}${tenantId}/export/`,
      {}
    );
  }

  listTenantContracts(tenantId: number): Observable<TenantContractRecord[]> {
    return this.http.get<TenantContractRecord[]>(
      `${this.baseUrl}${tenantId}/contracts/`
    );
  }

  createTenantContract(tenantId: number): Observable<TenantContractRecord> {
    return this.http.post<TenantContractRecord>(
      `${this.baseUrl}${tenantId}/contracts/`,
      {}
    );
  }

  getContract(contractId: number): Observable<TenantContractRecord> {
    const contractsUrl = environment.apiBaseUrl
      ? `${environment.apiBaseUrl}/control-panel/contracts/`
      : "/control-panel/contracts/";
    return this.http.get<TenantContractRecord>(`${contractsUrl}${contractId}/`);
  }

  sendContract(
    contractId: number,
    payload: { to_email: string; force_send?: boolean }
  ): Observable<TenantContractRecord & { email_log: ContractEmailLogRecord }> {
    const contractsUrl = environment.apiBaseUrl
      ? `${environment.apiBaseUrl}/control-panel/contracts/`
      : "/control-panel/contracts/";
    return this.http.post<TenantContractRecord & { email_log: ContractEmailLogRecord }>(
      `${contractsUrl}${contractId}/send/`,
      payload
    );
  }

  lookupCep(cep: string): Observable<{
    cep: string;
    logradouro: string;
    bairro: string;
    cidade: string;
    uf: string;
  }> {
    const digits = cep.replace(/\D/g, "");
    return this.http.get<{
      cep: string;
      logradouro: string;
      bairro: string;
      cidade: string;
      uf: string;
    }>(`${this.controlPanelCepBaseUrl}${digits}/`);
  }

  listTenantAudit(tenantId: number): Observable<AdminAuditEventRecord[]> {
    return this.http.get<AdminAuditEventRecord[]>(
      `${this.baseUrl}${tenantId}/audit/`
    );
  }

  listTenantNotes(tenantId: number): Observable<TenantInternalNoteRecord[]> {
    return this.http.get<TenantInternalNoteRecord[]>(
      `${this.baseUrl}${tenantId}/notes/`
    );
  }

  createTenantNote(
    tenantId: number,
    note: string
  ): Observable<TenantInternalNoteRecord> {
    return this.http.post<TenantInternalNoteRecord>(
      `${this.baseUrl}${tenantId}/notes/`,
      { note }
    );
  }

  listFeatureFlags(): Observable<FeatureFlagRecord[]> {
    return this.http.get<FeatureFlagRecord[]>(
      environment.apiBaseUrl
        ? `${environment.apiBaseUrl}/control-panel/features/`
        : "/control-panel/features/"
    );
  }

  listTenantFeatures(tenantId: number): Observable<TenantFeatureFlagRecord[]> {
    return this.http.get<TenantFeatureFlagRecord[]>(
      `${this.baseUrl}${tenantId}/features/`
    );
  }

  updateTenantFeature(
    tenantId: number,
    featureKey: string,
    enabled: boolean
  ): Observable<TenantFeatureFlagRecord> {
    return this.http.post<TenantFeatureFlagRecord>(
      `${this.baseUrl}${tenantId}/features/`,
      { feature_key: featureKey, enabled }
    );
  }

  getTenantLimits(tenantId: number): Observable<TenantOperationalSettingsRecord> {
    return this.http.get<TenantOperationalSettingsRecord>(
      `${this.baseUrl}${tenantId}/limits/`
    );
  }

  updateTenantLimits(
    tenantId: number,
    payload: Partial<TenantOperationalSettingsRecord>
  ): Observable<TenantOperationalSettingsRecord> {
    return this.http.post<TenantOperationalSettingsRecord>(
      `${this.baseUrl}${tenantId}/limits/`,
      payload
    );
  }

  listTenantIntegrations(tenantId: number): Observable<TenantIntegrationSecretRefRecord[]> {
    return this.http.get<TenantIntegrationSecretRefRecord[]>(
      `${this.baseUrl}${tenantId}/integrations/`
    );
  }

  upsertTenantIntegration(
    tenantId: number,
    payload: {
      provider: string;
      alias: string;
      secret_manager_ref: string;
      metadata_json?: Record<string, unknown>;
      is_active?: boolean;
    }
  ): Observable<TenantIntegrationSecretRefRecord> {
    return this.http.post<TenantIntegrationSecretRefRecord>(
      `${this.baseUrl}${tenantId}/integrations/`,
      payload
    );
  }

  listTenantChangelog(tenantId: number): Observable<TenantReleaseRecord[]> {
    return this.http.get<TenantReleaseRecord[]>(
      `${this.baseUrl}${tenantId}/changelog/`
    );
  }

  createTenantRelease(
    tenantId: number,
    payload: {
      backend_version: string;
      frontend_version?: string;
      git_sha?: string;
      source?: string;
      changelog?: string;
      changelog_json?: unknown;
      is_current?: boolean;
      deployed_at?: string;
    }
  ): Observable<TenantReleaseRecord> {
    return this.http.post<TenantReleaseRecord>(
      `${this.baseUrl}${tenantId}/changelog/`,
      payload
    );
  }

  listTenantAlerts(
    tenantId: number,
    status?: "OPEN" | "RESOLVED"
  ): Observable<TenantAlertEventRecord[]> {
    const suffix = status ? `?status=${status}` : "";
    return this.http.get<TenantAlertEventRecord[]>(
      `${this.baseUrl}${tenantId}/alerts/${suffix}`
    );
  }

  resolveTenantAlert(
    tenantId: number,
    alertId: number
  ): Observable<TenantAlertEventRecord> {
    return this.http.post<TenantAlertEventRecord>(
      `${this.baseUrl}${tenantId}/alerts/resolve/`,
      { alert_id: alertId }
    );
  }

  startTenantImpersonation(
    tenantId: number,
    payload?: { reason?: string; duration_minutes?: number }
  ): Observable<{
    tenant_code: string;
    portal_url: string;
    session: TenantImpersonationSessionRecord;
  }> {
    return this.http.post<{
      tenant_code: string;
      portal_url: string;
      session: TenantImpersonationSessionRecord;
    }>(`${this.baseUrl}${tenantId}/impersonate/`, payload ?? {});
  }

  stopTenantImpersonation(
    tenantId: number,
    sessionId?: number
  ): Observable<{ ended_sessions: number }> {
    return this.http.post<{ ended_sessions: number }>(
      `${this.baseUrl}${tenantId}/impersonate/stop/`,
      sessionId ? { session_id: sessionId } : {}
    );
  }
}
