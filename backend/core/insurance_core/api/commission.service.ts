import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface CommissionAccrual {
  id: number;
  amount: number;
  status: 'PENDING' | 'PAID' | 'CANCELLED';
  created_at: string;
  recipient: { id: number; name: string };
  policy_id?: number;
}

export interface PayoutBatch {
  id: number;
  status: 'DRAFT' | 'APPROVED' | 'PAID';
  total_amount: number;
  period_start: string;
  period_end: string;
  items_count: number;
}

export interface CreatePayoutBatchRequest {
  period_start: string;
  period_end: string;
  producer_id?: number;
}

export interface InsurerSettlementBatch {
  id: number;
  insurer_name: string;
  status: 'DRAFT' | 'APPROVED';
  total_amount: number;
  period_start: string;
  period_end: string;
}

export interface CreateSettlementBatchRequest {
  insurer_name: string;
  period_start: string;
  period_end: string;
}

export interface CommissionPlan {
  id: number;
  name: string;
  description?: string;
  default_percent: number;
}

@Injectable({
  providedIn: 'root'
})
export class CommissionService {
  private readonly API_URL = '/api/operational';

  constructor(private http: HttpClient) {}

  listAccruals(params: { period_start?: string; period_end?: string; producer_id?: number; policy_id?: number } = {}): Observable<CommissionAccrual[]> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) httpParams = httpParams.set(key, value.toString());
    });
    return this.http.get<CommissionAccrual[]>(`${this.API_URL}/commission-accruals/`, { params: httpParams });
  }

  // Payout Batches (Pagamento a Produtores)
  createPayoutBatch(data: CreatePayoutBatchRequest): Observable<PayoutBatch> {
    return this.http.post<PayoutBatch>(`${this.API_URL}/commission-payouts/`, data);
  }

  listPayoutBatches(): Observable<PayoutBatch[]> {
    return this.http.get<PayoutBatch[]>(`${this.API_URL}/commission-payouts/`);
  }

  getPayoutBatch(id: number): Observable<PayoutBatch & { items: CommissionAccrual[] }> {
    return this.http.get<PayoutBatch & { items: CommissionAccrual[] }>(`${this.API_URL}/commission-payouts/${id}/`);
  }

  approvePayoutBatch(id: number): Observable<PayoutBatch> {
    return this.http.post<PayoutBatch>(`${this.API_URL}/commission-payouts/${id}/approve/`, {});
  }

  // Insurer Settlements (Recebimento de Seguradoras)
  createInsurerSettlement(data: CreateSettlementBatchRequest): Observable<InsurerSettlementBatch> {
    return this.http.post<InsurerSettlementBatch>(`${this.API_URL}/insurer-settlements/`, data);
  }

  listInsurerSettlements(): Observable<InsurerSettlementBatch[]> {
    return this.http.get<InsurerSettlementBatch[]>(`${this.API_URL}/insurer-settlements/`);
  }

  getInsurerSettlement(id: number): Observable<InsurerSettlementBatch & { items: any[] }> {
    return this.http.get<InsurerSettlementBatch & { items: any[] }>(`${this.API_URL}/insurer-settlements/${id}/`);
  }

  approveInsurerSettlement(id: number): Observable<InsurerSettlementBatch> {
    return this.http.post<InsurerSettlementBatch>(`${this.API_URL}/insurer-settlements/${id}/approve/`, {});
  }

  // Commission Plans
  listPlans(): Observable<CommissionPlan[]> {
    return this.http.get<CommissionPlan[]>(`${this.API_URL}/commission-plans/`);
  }

  createPlan(data: Omit<CommissionPlan, 'id'>): Observable<CommissionPlan> {
    return this.http.post<CommissionPlan>(`${this.API_URL}/commission-plans/`, data);
  }

  updatePlan(id: number, data: Partial<CommissionPlan> & { recalculate_retroactive?: boolean }): Observable<CommissionPlan> {
    return this.http.patch<CommissionPlan>(`${this.API_URL}/commission-plans/${id}/`, data);
  }

  deletePlan(id: number): Observable<void> {
    return this.http.delete<void>(`${this.API_URL}/commission-plans/${id}/`);
  }
}