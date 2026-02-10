import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Observable, BehaviorSubject } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { CommissionService, PayoutBatch } from '../commission.service';
import { PermissionService } from '../../core/services/permission.service';

@Component({
  selector: 'app-payout-batches',
  template: `
    <div class="batches-container">
      <div class="header">
        <h2>Lotes de Pagamento (Payouts)</h2>
        <button *appHasPermission="'commission.payouts.create'" (click)="showModal = true" class="btn-primary">Novo Lote</button>
      </div>

      <table class="table" *ngIf="batches$ | async as batches">
        <thead>
          <tr>
            <th>ID</th>
            <th>Período</th>
            <th>Itens</th>
            <th>Total</th>
            <th>Status</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let batch of batches">
            <td>#{{ batch.id }}</td>
            <td>{{ batch.period_start | date:'dd/MM' }} a {{ batch.period_end | date:'dd/MM/yyyy' }}</td>
            <td>{{ batch.items_count }}</td>
            <td>{{ batch.total_amount | currency:'BRL' }}</td>
            <td><span class="badge" [ngClass]="'badge-' + batch.status.toLowerCase()">{{ batch.status }}</span></td>
            <td>
              <ng-container *appHasPermission="'commission.payouts.approve'">
                <button *ngIf="batch.status === 'DRAFT'" (click)="approve(batch)" class="btn-sm btn-success">Aprovar</button>
              </ng-container>
              <!-- View items logic could be added here -->
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Create Modal -->
      <div class="modal-backdrop" *ngIf="showModal">
        <div class="modal-content">
          <h3>Novo Lote de Pagamento</h3>
          <form [formGroup]="form" (ngSubmit)="create()">
            <div class="form-group">
              <label>Início do Período</label>
              <input type="date" formControlName="period_start" class="form-control">
            </div>
            <div class="form-group">
              <label>Fim do Período</label>
              <input type="date" formControlName="period_end" class="form-control">
            </div>
            <div class="form-group">
              <label>Produtor (Opcional)</label>
              <input type="number" formControlName="producer_id" class="form-control" placeholder="ID do Produtor">
            </div>
            <div class="modal-actions">
              <button type="button" (click)="showModal = false">Cancelar</button>
              <button type="submit" class="btn-primary" [disabled]="form.invalid">Gerar Lote</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .batches-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    .badge { padding: 4px 8px; border-radius: 12px; font-size: 0.85em; }
    .badge-draft { background: #e2e3e5; color: #383d41; }
    .badge-approved { background: #c3e6cb; color: #155724; }
    .badge-paid { background: #d4edda; color: #155724; }
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .btn-success { background: #28a745; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
    
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 400px; }
    .form-group { margin-bottom: 15px; }
    .form-control { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
  `]
})
export class PayoutBatchesComponent implements OnInit {
  batches$: Observable<PayoutBatch[]>;
  refresh$ = new BehaviorSubject<void>(undefined);
  showModal = false;
  form: FormGroup;

  constructor(
    private fb: FormBuilder, 
    private commissionService: CommissionService,
    private permissionService: PermissionService
  ) {
    this.form = this.fb.group({
      period_start: ['', Validators.required],
      period_end: ['', Validators.required],
      producer_id: ['']
    });
  }

  ngOnInit() {
    this.batches$ = this.refresh$.pipe(switchMap(() => this.commissionService.listPayoutBatches()));
  }

  create() {
    if (this.form.invalid) return;
    this.commissionService.createPayoutBatch(this.form.value).subscribe(() => { this.showModal = false; this.refresh$.next(); });
  }

  approve(batch: PayoutBatch) {
    if (confirm('Confirmar aprovação do lote?')) this.commissionService.approvePayoutBatch(batch.id).subscribe(() => this.refresh$.next());
  }
}