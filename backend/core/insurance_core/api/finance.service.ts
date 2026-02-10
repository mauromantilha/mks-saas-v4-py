import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, forkJoin } from 'rxjs';
import { map } from 'rxjs/operators';

export interface Installment {
  id: number;
  invoice_id: number;
  number: number;
  amount: number;
  due_date: string;
  status: 'OPEN' | 'PAID' | 'CANCELLED' | 'OVERDUE';
  paid_amount?: number;
  paid_date?: string;
}

export interface LedgerEntry {
  id: number;
  account_code: string;
  description: string;
  debit: number;
  credit: number;
  transaction_date: string;
}

export interface RegisterPaymentRequest {
  amount: number;
  payment_date: string;
  method?: string;
  notes?: string;
}

export interface BankTransaction {
  id: number;
  date: string;
  amount: number;
  description: string;
  status: 'PENDING' | 'RECONCILED';
  external_id: string;
}

export interface CashFlowData {
  period: string;
  income: number;
  expense: number;
  balance: number;
}

export interface FinanceAlert {
  type: 'OVERDUE' | 'DUE_SOON';
  count: number;
  amount: number;
  items: Installment[];
}

@Injectable({
  providedIn: 'root'
})
export class FinanceService {
  private readonly API_URL = '/api/finance';

  constructor(private http: HttpClient) {}

  listInstallments(params: { policy_id?: number; status?: string; due_date_start?: string; due_date_end?: string } = {}): Observable<Installment[]> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) httpParams = httpParams.set(key, value.toString());
    });
    return this.http.get<Installment[]>(`${this.API_URL}/installments/`, { params: httpParams });
  }

  registerPayment(installmentId: number, data: RegisterPaymentRequest): Observable<Installment> {
    return this.http.post<Installment>(`${this.API_URL}/installments/${installmentId}/pay/`, data);
  }

  listLedger(params: { account_code?: string; start_date?: string; end_date?: string } = {}): Observable<LedgerEntry[]> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) httpParams = httpParams.set(key, value.toString());
    });
    return this.http.get<LedgerEntry[]>(`${this.API_URL}/ledger/`, { params: httpParams });
  }

  listBankTransactions(params: { status?: string; start_date?: string; end_date?: string } = {}): Observable<BankTransaction[]> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) httpParams = httpParams.set(key, value.toString());
    });
    return this.http.get<BankTransaction[]>(`${this.API_URL}/banking/transactions/`, { params: httpParams });
  }

  reconcile(transactionId: number, installmentId: number): Observable<void> {
    return this.http.post<void>(`${this.API_URL}/banking/transactions/${transactionId}/reconcile/`, { installment_id: installmentId });
  }

  importOfx(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.API_URL}/banking/import-ofx/`, formData);
  }

  getCashFlow(months: number = 6): Observable<CashFlowData[]> {
    const params = new HttpParams().set('months', months.toString());
    return this.http.get<CashFlowData[]>(`${this.API_URL}/cash-flow/`, { params });
  }

  getAlerts(): Observable<FinanceAlert[]> {
    const today = new Date().toISOString().split('T')[0];
    const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    return forkJoin({
      overdue: this.listInstallments({ status: 'OVERDUE' }),
      dueSoon: this.listInstallments({ status: 'OPEN', due_date_start: today, due_date_end: nextWeek })
    }).pipe(
      map(results => [
        { type: 'OVERDUE' as const, count: results.overdue.length, amount: results.overdue.reduce((acc, i) => acc + i.amount, 0), items: results.overdue },
        { type: 'DUE_SOON' as const, count: results.dueSoon.length, amount: results.dueSoon.reduce((acc, i) => acc + i.amount, 0), items: results.dueSoon }
      ])
    );
  }
}