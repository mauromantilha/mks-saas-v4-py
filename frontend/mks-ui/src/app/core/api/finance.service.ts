import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import { ReceivableInvoiceRecord } from "./finance.types";

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
    return this.http.get<ReceivableInvoiceRecord[]>(`${this.apiBase}/invoices/`, {
      params: httpParams,
    });
  }
}
