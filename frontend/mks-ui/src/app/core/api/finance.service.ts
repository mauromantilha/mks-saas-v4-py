import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";
import { map } from "rxjs/operators";

import { environment } from "../../../environments/environment";
import { normalizeListResponse } from "../../shared/api/response-normalizers";
import {
  PayableRecord,
  PolicyFinanceSummaryRecord,
  ReceivableInstallmentStatus,
  ReceivableInstallmentRecord,
  ReceivableInvoiceRecord,
} from "./finance.types";

@Injectable({ providedIn: "root" })
export class FinanceService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/finance`
    : "/api/finance";

  constructor(private readonly http: HttpClient) {}

  listInvoices(params?: { payer_id?: number | null }): Observable<ReceivableInvoiceRecord[]> {
    let httpParams = new HttpParams();
    if (params?.payer_id) {
      httpParams = httpParams.set("payer_id", String(params.payer_id));
    }
    return this.http
      .get<unknown>(`${this.apiBase}/invoices/`, {
        params: httpParams,
      })
      .pipe(
        map((response) => normalizeListResponse<ReceivableInvoiceRecord>(response).results)
      );
  }

  listPayables(params?: {
    status?: string;
    recipient_id?: number | null;
    q?: string;
  }): Observable<PayableRecord[]> {
    let httpParams = new HttpParams();
    if (params?.status?.trim()) {
      httpParams = httpParams.set("status", params.status.trim());
    }
    if (params?.recipient_id) {
      httpParams = httpParams.set("recipient_id", String(params.recipient_id));
    }
    if (params?.q?.trim()) {
      httpParams = httpParams.set("q", params.q.trim());
    }
    return this.http
      .get<unknown>(`${this.apiBase}/payables/`, {
        params: httpParams,
      })
      .pipe(map((response) => normalizeListResponse<PayableRecord>(response).results));
  }

  listInstallments(params?: {
    policy_id?: number | null;
    insurer_id?: number | null;
    status?: ReceivableInstallmentStatus | "DELINQUENT" | "";
    delinquent_only?: boolean;
  }): Observable<ReceivableInstallmentRecord[]> {
    let httpParams = new HttpParams();
    if (params?.policy_id) {
      httpParams = httpParams.set("policy_id", String(params.policy_id));
    }
    if (params?.insurer_id) {
      httpParams = httpParams.set("insurer_id", String(params.insurer_id));
    }
    if (params?.status?.trim()) {
      httpParams = httpParams.set("status", params.status.trim());
    }
    if (params?.delinquent_only) {
      httpParams = httpParams.set("delinquent_only", "true");
    }
    return this.http
      .get<unknown>(`${this.apiBase}/installments/`, {
        params: httpParams,
      })
      .pipe(
        map(
          (response) =>
            normalizeListResponse<ReceivableInstallmentRecord>(response).results
        )
      );
  }

  settleInstallment(installmentId: number): Observable<ReceivableInstallmentRecord> {
    return this.http.post<ReceivableInstallmentRecord>(
      `${this.apiBase}/installments/${installmentId}/settle/`,
      {}
    );
  }

  listPolicySummary(policyIds: number[]): Observable<PolicyFinanceSummaryRecord[]> {
    let params = new HttpParams();
    if (policyIds.length > 0) {
      params = params.set("policy_ids", policyIds.join(","));
    }
    return this.http.get<PolicyFinanceSummaryRecord[]>(`${this.apiBase}/policies/summary/`, {
      params,
    });
  }
}
