import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';

export interface Policy {
  id: number;
  policy_number: string;
  status: 'QUOTED' | 'ISSUED' | 'ACTIVE' | 'CANCELLED' | 'EXPIRED';
  start_date: string;
  end_date: string;
  customer: { id: number; name: string };
  insurer: { id: number; name: string };
  product: { id: number; name: string };
  premium_total?: number;
}

export interface CreatePolicyRequest {
  customer_id: number;
  insurer_id: number;
  product_id: number;
  branch_id: number;
  start_date: string;
  end_date: string;
  billing_config?: {
    installments_count: number;
    premium_total: number;
    commission_rate_percent: number;
    first_installment_due_date: string;
  };
}

export interface EndorsementRequest {
  endorsement_type: 'PREMIUM_INCREASE' | 'PREMIUM_DECREASE' | 'NO_PREMIUM_MOVEMENT' | 'HEALTH_ADD_BENEFICIARY';
  effective_date: string;
  premium_delta?: number;
  description?: string;
}

export interface CancelPolicyRequest {
  effective_date: string;
  reason?: string;
}

export interface PolicyListParams {
  page?: number;
  page_size?: number;
  status?: string;
  branch_id?: number;
  insurer_id?: number;
  start_date_after?: string;
  start_date_before?: string;
  search?: string;
}

export interface PolicyFormOptions {
  customers: any[];
  insurers: any[];
  products: any[];
  branches: any[];
  producers: any[];
}

@Injectable({
  providedIn: 'root'
})
export class PolicyService {
  private readonly API_URL = '/api/insurance/policies';

  constructor(private http: HttpClient) {}

  list(params: PolicyListParams = {}): Observable<any> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        httpParams = httpParams.set(key, value.toString());
      }
    });
    return this.http.get<any>(this.API_URL + '/', { params: httpParams });
  }

  get(id: number): Observable<Policy> {
    return this.http.get<Policy>(`${this.API_URL}/${id}/`);
  }

  create(data: CreatePolicyRequest): Observable<Policy> {
    return this.http.post<Policy>(this.API_URL + '/', data);
  }

  issue(id: number): Observable<Policy> {
    return this.http.post<Policy>(`${this.API_URL}/${id}/issue/`, {});
  }

  applyEndorsement(policyId: number, data: EndorsementRequest): Observable<any> {
    return this.http.post(`${this.API_URL}/${policyId}/endorsements/`, data);
  }

  cancel(id: number, data: CancelPolicyRequest): Observable<Policy> {
    return this.http.post<Policy>(`${this.API_URL}/${id}/cancel/`, data);
  }

  previewEndorsement(policyId: number, data: EndorsementRequest): Observable<any> {
    return this.http.post(`${this.API_URL}/${policyId}/endorsements/preview/`, data);
  }

  listEndorsements(policyId: number): Observable<any[]> {
    return this.http.get<any[]>(`${this.API_URL}/${policyId}/endorsements/`);
  }

  getFormOptions(): Observable<PolicyFormOptions> {
    return forkJoin({
      customers: this.http.get<any[]>('/api/customers/'),
      insurers: this.http.get<any[]>('/api/insurance/insurers/'),
      products: this.http.get<any[]>('/api/insurance/products/'),
      branches: this.http.get<any[]>('/api/insurance/branches/'),
      producers: this.http.get<any[]>('/api/users/?role=producer') // Ajustar endpoint conforme real
    });
  }
}