import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup } from '@angular/forms';
import { Observable } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';
import { CommissionService, CommissionAccrual } from '../commission.service';

@Component({
  selector: 'app-accruals',
  template: `
    <div class="accruals-container">
      <h2>Extrato de Comissões (Accruals)</h2>

      <form [formGroup]="filterForm" class="filters">
        <div class="filter-group">
          <label>Período (De)</label>
          <input type="date" formControlName="period_start" class="form-control">
        </div>
        <div class="filter-group">
          <label>Período (Até)</label>
          <input type="date" formControlName="period_end" class="form-control">
        </div>
        <div class="filter-group">
          <label>Produtor (ID)</label>
          <input type="number" formControlName="producer_id" class="form-control" placeholder="ID">
        </div>
        <div class="filter-group">
          <label>Apólice (ID)</label>
          <input type="number" formControlName="policy_id" class="form-control" placeholder="ID">
        </div>
      </form>

      <table class="table" *ngIf="accruals$ | async as accruals">
        <thead>
          <tr>
            <th>ID</th>
            <th>Data</th>
            <th>Produtor</th>
            <th>Apólice</th>
            <th>Valor</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let item of accruals">
            <td>#{{ item.id }}</td>
            <td>{{ item.created_at | date:'dd/MM/yyyy' }}</td>
            <td>{{ item.recipient.name }}</td>
            <td>#{{ item.policy_id }}</td>
            <td>{{ item.amount | currency:'BRL' }}</td>
            <td>
              <span class="badge" [ngClass]="'badge-' + item.status.toLowerCase()">{{ item.status }}</span>
            </td>
          </tr>
          <tr *ngIf="accruals.length === 0">
            <td colspan="6" class="text-center">Nenhum registro encontrado.</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .accruals-container { padding: 20px; }
    .filters { display: flex; gap: 15px; margin-bottom: 20px; background: #f9f9f9; padding: 15px; border-radius: 8px; flex-wrap: wrap; }
    .filter-group { display: flex; flex-direction: column; }
    .form-control { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    .badge { padding: 4px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }
    .badge-pending { background: #fff3cd; color: #856404; }
    .badge-paid { background: #d4edda; color: #155724; }
    .badge-cancelled { background: #f8d7da; color: #721c24; }
  `]
})
export class AccrualsComponent implements OnInit {
  filterForm: FormGroup;
  accruals$: Observable<CommissionAccrual[]>;

  constructor(private fb: FormBuilder, private commissionService: CommissionService) {
    this.filterForm = this.fb.group({ period_start: [''], period_end: [''], producer_id: [''], policy_id: [''] });
  }

  ngOnInit() {
    this.accruals$ = this.filterForm.valueChanges.pipe(startWith(this.filterForm.value), switchMap(val => this.commissionService.listAccruals(val)));
  }
}