import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Observable, BehaviorSubject } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { CommissionService, CommissionPlan } from '../commission.service';
import { PermissionService } from '../../core/services/permission.service';

@Component({
  selector: 'app-commission-plans',
  template: `
    <div class="plans-container">
      <div class="header">
        <h2>Planos de Comissão</h2>
        <button *appHasPermission="'commission.plans.edit'" (click)="openModal()" class="btn-primary">Novo Plano</button>
      </div>

      <table class="table" *ngIf="plans$ | async as plans">
        <thead>
          <tr>
            <th>Nome</th>
            <th>Descrição</th>
            <th>% Padrão</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let plan of plans">
            <td>{{ plan.name }}</td>
            <td>{{ plan.description }}</td>
            <td>{{ plan.default_percent }}%</td>
            <td>
              <ng-container *appHasPermission="'commission.plans.edit'">
                <button (click)="openModal(plan)" class="btn-icon">✏️</button>
                <button (click)="delete(plan)" class="btn-icon text-danger">🗑️</button>
              </ng-container>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Modal -->
      <div class="modal-backdrop" *ngIf="showModal">
        <div class="modal-content">
          <h3>{{ editingId ? 'Editar' : 'Novo' }} Plano</h3>
          <form [formGroup]="form" (ngSubmit)="save()">
            <div class="form-group">
              <label>Nome</label>
              <input formControlName="name" class="form-control">
            </div>
            <div class="form-group">
              <label>Descrição</label>
              <textarea formControlName="description" class="form-control"></textarea>
            </div>
            <div class="form-group">
              <label>% Padrão</label>
              <input type="number" formControlName="default_percent" class="form-control">
            </div>
            <div class="form-group checkbox-group" *ngIf="editingId">
              <input type="checkbox" formControlName="recalculate_retroactive" id="recalc">
              <label for="recalc">Recalcular comissões retroativas?</label>
              <small class="help-text">Isso afetará lançamentos em aberto associados a este plano.</small>
            </div>
            <div class="modal-actions">
              <button type="button" (click)="showModal = false">Cancelar</button>
              <button type="submit" class="btn-primary" [disabled]="form.invalid">Salvar</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .plans-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 1.1em; margin-right: 5px; }
    .text-danger { color: #dc3545; }
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 400px; }
    .form-group { margin-bottom: 15px; }
    .form-control { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
    .checkbox-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .checkbox-group input { width: auto; margin: 0; }
    .checkbox-group label { margin: 0; font-weight: normal; }
    .help-text { width: 100%; font-size: 0.85em; color: #666; margin-left: 20px; }
  `]
})
export class CommissionPlansComponent implements OnInit {
  plans$: Observable<CommissionPlan[]>;
  refresh$ = new BehaviorSubject<void>(undefined);
  showModal = false;
  form: FormGroup;
  editingId: number | null = null;

  constructor(private fb: FormBuilder, private commissionService: CommissionService, private permissionService: PermissionService) {
    this.form = this.fb.group({ 
      name: ['', Validators.required], 
      description: [''], 
      default_percent: [0, Validators.required],
      recalculate_retroactive: [false]
    });
  }

  ngOnInit() { this.plans$ = this.refresh$.pipe(switchMap(() => this.commissionService.listPlans())); }

  openModal(plan?: CommissionPlan) {
    this.editingId = plan ? plan.id : null;
    this.form.reset(plan || { default_percent: 0, recalculate_retroactive: false });
    this.showModal = true;
  }

  save() { 
    if (this.form.valid) { 
      const val = this.form.value;
      if (val.recalculate_retroactive && !confirm('Atenção: O recálculo retroativo pode alterar valores de comissões pendentes. Deseja continuar?')) return;
      const obs = this.editingId ? this.commissionService.updatePlan(this.editingId, val) : this.commissionService.createPlan(val); 
      obs.subscribe(() => { this.showModal = false; this.refresh$.next(); }); 
    } 
  }
  delete(plan: CommissionPlan) { if (confirm('Excluir plano?')) this.commissionService.deletePlan(plan.id).subscribe(() => this.refresh$.next()); }
}