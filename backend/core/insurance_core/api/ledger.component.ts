import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { Observable } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';
import { FinanceService, LedgerEntry } from '../finance.service';

@Component({
  selector: 'app-ledger',
  template: `
    <div class="ledger-container">
      <h2>Razão Contábil (Ledger)</h2>

      <form [formGroup]="filterForm" class="filters">
        <div class="filter-group">
          <label>Conta Contábil</label>
          <input formControlName="account_code" class="form-control" placeholder="Ex: 1.1.01">
        </div>
        <div class="filter-group">
          <label>Data Início</label>
          <input type="date" formControlName="start_date" class="form-control">
        </div>
        <div class="filter-group">
          <label>Data Fim</label>
          <input type="date" formControlName="end_date" class="form-control">
        </div>
      </form>

      <table class="table" *ngIf="entries$ | async as entries">
        <thead>
          <tr>
            <th>Data</th>
            <th>Conta</th>
            <th>Descrição</th>
            <th class="text-right">Débito</th>
            <th class="text-right">Crédito</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let entry of entries">
            <td>{{ entry.transaction_date | date:'dd/MM/yyyy HH:mm' }}</td>
            <td>{{ entry.account_code }}</td>
            <td>{{ entry.description }}</td>
            <td class="text-right">{{ entry.debit > 0 ? (entry.debit | currency:'BRL') : '-' }}</td>
            <td class="text-right">{{ entry.credit > 0 ? (entry.credit | currency:'BRL') : '-' }}</td>
          </tr>
          <tr *ngIf="entries.length === 0">
            <td colspan="5" class="text-center">Nenhum lançamento encontrado.</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .ledger-container { padding: 20px; }
    .filters { display: flex; gap: 15px; margin-bottom: 20px; background: #f9f9f9; padding: 15px; border-radius: 8px; }
    .filter-group { display: flex; flex-direction: column; }
    .form-control { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 10px; border-bottom: 1px solid #eee; text-align: left; }
    .text-right { text-align: right; }
    .text-center { text-align: center; color: #666; padding: 20px; }
  `]
})
export class LedgerComponent implements OnInit {
  filterForm: FormGroup;
  entries$: Observable<LedgerEntry[]>;

  constructor(private fb: FormBuilder, private financeService: FinanceService) {
    this.filterForm = this.fb.group({ account_code: [''], start_date: [''], end_date: [''] });
  }

  ngOnInit() {
    this.entries$ = this.filterForm.valueChanges.pipe(
      startWith(this.filterForm.value),
      switchMap(filters => this.financeService.listLedger(filters))
    );
  }
}