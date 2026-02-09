import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  CepLookupResponse,
  CreateInsurerPayload,
  CreateEndorsementPayload,
  CreatePolicyCoveragePayload,
  CreatePolicyDocumentRequirementPayload,
  CreatePolicyItemPayload,
  CreatePolicyPayload,
  EndorsementRecord,
  InsuranceProductRecord,
  InsurerRecord,
  InsurerStatus,
  PolicyCoverageRecord,
  PolicyDocumentRequirementRecord,
  PolicyItemRecord,
  PolicyRecord,
  PolicyStatus,
  ProductCoverageRecord,
  TransitionPolicyPayload,
  UpdatePolicyPayload,
  UpdateInsurerPayload,
  LineOfBusiness,
  InsuranceProductStatus,
} from "./insurance-core.types";

@Injectable({ providedIn: "root" })
export class InsuranceCoreService {
  private readonly apiRoot = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";
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

  lookupCep(cep: string): Observable<CepLookupResponse> {
    const encoded = encodeURIComponent((cep || "").trim());
    return this.http.get<CepLookupResponse>(`${this.apiRoot}/utils/cep/${encoded}/`);
  }

  deactivateInsurer(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/insurers/${id}/`);
  }

  listProducts(filters?: {
    q?: string;
    insurer_id?: number | "";
    status?: InsuranceProductStatus | "";
    line_of_business?: LineOfBusiness | "";
  }): Observable<InsuranceProductRecord[]> {
    let params = new HttpParams();
    if (filters?.q?.trim()) {
      params = params.set("q", filters.q.trim());
    }
    if (filters?.insurer_id) {
      params = params.set("insurer_id", String(filters.insurer_id));
    }
    if (filters?.status?.trim()) {
      params = params.set("status", filters.status.trim());
    }
    if (filters?.line_of_business?.trim()) {
      params = params.set("line_of_business", filters.line_of_business.trim());
    }
    return this.http.get<InsuranceProductRecord[]>(`${this.apiBase}/products/`, { params });
  }

  listCoverages(filters?: { product_id?: number | "" }): Observable<ProductCoverageRecord[]> {
    let params = new HttpParams();
    if (filters?.product_id) {
      params = params.set("product_id", String(filters.product_id));
    }
    return this.http.get<ProductCoverageRecord[]>(`${this.apiBase}/coverages/`, { params });
  }

  listPolicies(filters?: {
    q?: string;
    status?: PolicyStatus | "";
    insurer_id?: number | "";
    insured_party_id?: number | "";
  }): Observable<PolicyRecord[]> {
    let params = new HttpParams();
    if (filters?.q?.trim()) {
      params = params.set("q", filters.q.trim());
    }
    if (filters?.status?.trim()) {
      params = params.set("status", filters.status.trim());
    }
    if (filters?.insurer_id) {
      params = params.set("insurer_id", String(filters.insurer_id));
    }
    if (filters?.insured_party_id) {
      params = params.set("insured_party_id", String(filters.insured_party_id));
    }
    return this.http.get<PolicyRecord[]>(`${this.apiBase}/policies/`, { params });
  }

  createPolicy(payload: CreatePolicyPayload): Observable<PolicyRecord> {
    return this.http.post<PolicyRecord>(`${this.apiBase}/policies/`, payload);
  }

  updatePolicy(id: number, payload: UpdatePolicyPayload): Observable<PolicyRecord> {
    return this.http.patch<PolicyRecord>(`${this.apiBase}/policies/${id}/`, payload);
  }

  transitionPolicy(id: number, payload: TransitionPolicyPayload): Observable<PolicyRecord> {
    return this.http.post<PolicyRecord>(`${this.apiBase}/policies/${id}/transition/`, payload);
  }

  deletePolicy(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/policies/${id}/`);
  }

  listPolicyItems(policyId: number): Observable<PolicyItemRecord[]> {
    const params = new HttpParams().set("policy_id", String(policyId));
    return this.http.get<PolicyItemRecord[]>(`${this.apiBase}/policy-items/`, { params });
  }

  createPolicyItem(payload: CreatePolicyItemPayload): Observable<PolicyItemRecord> {
    return this.http.post<PolicyItemRecord>(`${this.apiBase}/policy-items/`, payload);
  }

  deletePolicyItem(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/policy-items/${id}/`);
  }

  listPolicyCoverages(policyId: number): Observable<PolicyCoverageRecord[]> {
    const params = new HttpParams().set("policy_id", String(policyId));
    return this.http.get<PolicyCoverageRecord[]>(`${this.apiBase}/policy-coverages/`, { params });
  }

  createPolicyCoverage(payload: CreatePolicyCoveragePayload): Observable<PolicyCoverageRecord> {
    return this.http.post<PolicyCoverageRecord>(`${this.apiBase}/policy-coverages/`, payload);
  }

  deletePolicyCoverage(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/policy-coverages/${id}/`);
  }

  listPolicyDocumentRequirements(policyId: number): Observable<PolicyDocumentRequirementRecord[]> {
    const params = new HttpParams().set("policy_id", String(policyId));
    return this.http.get<PolicyDocumentRequirementRecord[]>(
      `${this.apiBase}/policy-document-requirements/`,
      { params }
    );
  }

  createPolicyDocumentRequirement(
    payload: CreatePolicyDocumentRequirementPayload
  ): Observable<PolicyDocumentRequirementRecord> {
    return this.http.post<PolicyDocumentRequirementRecord>(
      `${this.apiBase}/policy-document-requirements/`,
      payload
    );
  }

  deletePolicyDocumentRequirement(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/policy-document-requirements/${id}/`);
  }

  listEndorsements(policyId: number): Observable<EndorsementRecord[]> {
    const params = new HttpParams().set("policy_id", String(policyId));
    return this.http.get<EndorsementRecord[]>(`${this.apiBase}/endorsements/`, { params });
  }

  createEndorsement(payload: CreateEndorsementPayload): Observable<EndorsementRecord> {
    return this.http.post<EndorsementRecord>(`${this.apiBase}/endorsements/`, payload);
  }

  deleteEndorsement(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiBase}/endorsements/${id}/`);
  }
}
