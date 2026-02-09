import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  FiscalDocumentRecord,
  RetryFiscalResponse,
  TenantFiscalConfigRecord,
  UpsertTenantFiscalConfigPayload,
} from "./finance-fiscal.types";

@Injectable({ providedIn: "root" })
export class FinanceFiscalService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/finance`
    : "/api/finance";

  constructor(private readonly http: HttpClient) {}

  getActiveConfig(): Observable<TenantFiscalConfigRecord> {
    return this.http.get<TenantFiscalConfigRecord>(`${this.apiBase}/fiscal/config/`);
  }

  upsertConfig(payload: UpsertTenantFiscalConfigPayload): Observable<TenantFiscalConfigRecord> {
    return this.http.post<TenantFiscalConfigRecord>(`${this.apiBase}/fiscal/config/`, payload);
  }

  listDocuments(filters?: {
    status?: string;
    invoice_id?: string;
    q?: string;
  }): Observable<FiscalDocumentRecord[]> {
    let params = new HttpParams();
    if (filters?.status?.trim()) {
      params = params.set("status", filters.status.trim());
    }
    if (filters?.invoice_id?.trim()) {
      params = params.set("invoice_id", filters.invoice_id.trim());
    }
    if (filters?.q?.trim()) {
      params = params.set("q", filters.q.trim());
    }
    return this.http.get<FiscalDocumentRecord[]>(`${this.apiBase}/fiscal/`, { params });
  }

  issue(invoiceId: number): Observable<FiscalDocumentRecord> {
    return this.http.post<FiscalDocumentRecord>(`${this.apiBase}/fiscal/issue/`, {
      invoice_id: invoiceId,
    });
  }

  cancel(documentId: number): Observable<FiscalDocumentRecord> {
    return this.http.post<FiscalDocumentRecord>(`${this.apiBase}/fiscal/${documentId}/cancel/`, {});
  }

  retry(documentId: number): Observable<RetryFiscalResponse> {
    return this.http.post<RetryFiscalResponse>(`${this.apiBase}/fiscal/${documentId}/retry/`, {});
  }
}

