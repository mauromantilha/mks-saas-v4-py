import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { Observable, BehaviorSubject, combineLatest } from 'rxjs';
import { switchMap, startWith, tap } from 'rxjs/operators';
import { FinanceService, Installment } from '../finance.service';
import { TableColumn } from '../app-table.component';

@Component({
  selector: 'app-finance-installments',
  template: `
    <div class="receivables-container">
      <h2>Contas a Receber</h2>

      <app-filter-bar (search)="refresh()" (clear)="clearFilters()">
        <form [formGroup]="filterForm" class="filter-form">
          <mat-form-field appearance="outline">
            <mat-label>Status</mat-label>
            <mat-select formControlName="status">
              <mat-option value="">Todos</mat-option>
              <mat-option value="OPEN">Aberto</mat-option>
              <mat-option value="OVERDUE">Vencido</mat-option>
              <mat-option value="PAID">Pago</mat-option>
              <mat-option value="CANCELLED">Cancelado</mat-option>
            </mat-select>
          </mat-form-field>
          
          <mat-form-field appearance="outline">
            <mat-label>Vencimento (De)</mat-label>
            <input matInput type="date" formControlName="due_date_start">
          </mat-form-field>
          
          <mat-form-field appearance="outline">
            <mat-label>Vencimento (Até)</mat-label>
            <input matInput type="date" formControlName="due_date_end">
          </mat-form-field>
          
          <mat-form-field appearance="outline" class="small-input">
            <mat-label>Apólice (ID)</mat-label>
            <input matInput type="number" formControlName="policy_id">
          </mat-form-field>
        </form>
      </app-filter-bar>

      <app-table
        [columns]="columns"
        [data]="(installments$ | async) || []"
        [isLoading]="isLoading"
        [showFilter]="false"
        (rowClick)="onRowClick($event)">
      </app-table>

      <app-payment-modal
        *ngIf="selectedInstallment"
        [installment]="selectedInstallment"
        [policyId]="selectedInstallment.policy_id || 0" 
        (confirm)="onPaymentConfirmed()"
        (cancel)="selectedInstallment = null">
      </app-payment-modal>
    </div>
  `,
  styles: [`
    .receivables-container { padding: 20px; }
    .filter-form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; width: 100%; }
    .small-input { width: 120px; }
    ::ng-deep .filter-form .mat-mdc-form-field-subscript-wrapper { display: none; }
  `]
})
export class FinanceInstallmentsComponent implements OnInit {
  filterForm: FormGroup;
  installments$: Observable<Installment[]>;
  refresh$ = new BehaviorSubject<void>(undefined);
  selectedInstallment: any = null;
  isLoading = false;

  columns: TableColumn[] = [
    { def: 'policy_id', label: 'Apólice', format: (row) => `#${row.policy_id}` },
    { def: 'number', label: 'Parcela' },
    { def: 'due_date', label: 'Vencimento', format: (row) => new Date(row.due_date).toLocaleDateString() },
    { def: 'amount', label: 'Valor', format: (row) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(row.amount) },
    { def: 'status', label: 'Status' },
  ];

  constructor(private fb: FormBuilder, private financeService: FinanceService) {
    this.filterForm = this.fb.group({ status: ['OPEN'], due_date_start: [''], due_date_end: [''], policy_id: [''] });
  }

  ngOnInit() {
    const filters$ = this.filterForm.valueChanges.pipe(startWith(this.filterForm.value));
    this.installments$ = combineLatest([filters$, this.refresh$]).pipe(
      tap(() => this.isLoading = true),
      switchMap(([filters]) => this.financeService.listInstallments(filters).pipe(
        tap(() => this.isLoading = false)
      ))
    );
  }

  refresh() { this.refresh$.next(); }
  clearFilters() { this.filterForm.reset({ status: 'OPEN' }); }

  onRowClick(row: Installment) {
    if (row.status === 'OPEN' || row.status === 'OVERDUE') {
      this.selectedInstallment = row;
    }
  }

  onPaymentConfirmed() { this.selectedInstallment = null; this.refresh$.next(); }
}