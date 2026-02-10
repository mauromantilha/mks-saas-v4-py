import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Observable, BehaviorSubject } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { CommissionService, InsurerSettlementBatch } from '../commission.service';
import { PermissionService } from '../../core/services/permission.service';

@Component({
  selector: 'app-insurer-settlements',
  template: `
    <div class="settlements-container">
      <div class="header">
        <h2>Repasses de Seguradoras</h2>
        <button *appHasPermission="'commission.settlements.create'" (click)="showModal = true" class="btn-primary">Novo Repasse</button>
      </div>

      <table class="table" *ngIf="settlements$ | async as settlements">
        <thead>
          <tr>
            <th>ID</th>
            <th>Seguradora</th>
            <th>Período</th>
            <th>Total</th>
            <th>Status</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let item of settlements">
            <td>#{{ item.id }}</td>
            <td>{{ item.insurer_name }}</td>
            <td>{{ item.period_start | date:'dd/MM' }} a {{ item.period_end | date:'dd/MM/yyyy' }}</td>
            <td>{{ item.total_amount | currency:'BRL' }}</td>
            <td><span class="badge" [ngClass]="'badge-' + item.status.toLowerCase()">{{ item.status }}</span></td>
            <td>
              <ng-container *appHasPermission="'commission.settlements.approve'">
                <button *ngIf="item.status === 'DRAFT'" (click)="approve(item)" class="btn-sm btn-success">Aprovar</button>
              </ng-container>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Create Modal -->
      <div class="modal-backdrop" *ngIf="showModal">
        <div class="modal-content">
          <h3>Novo Repasse</h3>
          <form [formGroup]="form" (ngSubmit)="create()">
            <div class="form-group">
              <label>Seguradora</label>
              <input formControlName="insurer_name" class="form-control" placeholder="Nome da Seguradora">
            </div>
            <div class="form-group">
              <label>Início do Período</label>
              <input type="date" formControlName="period_start" class="form-control">
            </div>
            <div class="form-group">
              <label>Fim do Período</label>
              <input type="date" formControlName="period_end" class="form-control">
            </div>
            <div class="modal-actions">
              <button type="button" (click)="showModal = false">Cancelar</button>
              <button type="submit" class="btn-primary" [disabled]="form.invalid">Criar</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .settlements-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    .badge { padding: 4px 8px; border-radius: 12px; font-size: 0.85em; }
    .badge-draft { background: #e2e3e5; color: #383d41; }
    .badge-approved { background: #c3e6cb; color: #155724; }
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .btn-success { background: #28a745; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
    
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 400px; }
    .form-group { margin-bottom: 15px; }
    .form-control { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
  `]
})
export class InsurerSettlementsComponent implements OnInit {
  settlements$: Observable<InsurerSettlementBatch[]>;
  refresh$ = new BehaviorSubject<void>(undefined);
  showModal = false;
  form: FormGroup;

  constructor(
    private fb: FormBuilder, 
    private commissionService: CommissionService,
    private permissionService: PermissionService
  ) {
    this.form = this.fb.group({ insurer_name: ['', Validators.required], period_start: ['', Validators.required], period_end: ['', Validators.required] });
  }

  ngOnInit() {
    this.settlements$ = this.refresh$.pipe(switchMap(() => this.commissionService.listInsurerSettlements()));
  }

  create() { if (this.form.valid) this.commissionService.createInsurerSettlement(this.form.value).subscribe(() => { this.showModal = false; this.refresh$.next(); }); }
  approve(item: InsurerSettlementBatch) { if (confirm('Aprovar repasse?')) this.commissionService.approveInsurerSettlement(item.id).subscribe(() => this.refresh$.next()); }
}