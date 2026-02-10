import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { PolicyService, EndorsementRequest, CancelPolicyRequest } from '../policy.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-endorsement-modal',
  template: `
    <div class="modal-backdrop">
      <div class="modal-content">
        <h3>Novo Endosso</h3>
        
        <form [formGroup]="form" (ngSubmit)="onSubmit()">
          <div class="form-group">
            <label>Tipo de Endosso</label>
            <select formControlName="endorsement_type" class="form-control" (change)="onTypeChange()">
              <option value="PREMIUM_INCREASE">Aumento de Prêmio</option>
              <option value="PREMIUM_DECREASE">Redução de Prêmio</option>
              <option value="NO_PREMIUM_MOVEMENT">Sem Movimento Financeiro</option>
              <option value="CANCELLATION_ENDORSEMENT">Cancelamento</option>
              <option *ngIf="isHealth" value="HEALTH_ADD_BENEFICIARY">Inclusão de Beneficiário</option>
            </select>
          </div>

          <div class="form-group">
            <label>Data de Efetivação</label>
            <input type="date" formControlName="effective_date" class="form-control">
          </div>

          <!-- Fields for Financial Movement -->
          <div class="form-group" *ngIf="showPremiumField">
            <label>Valor do Ajuste (Delta R$)</label>
            <input type="number" formControlName="premium_delta" class="form-control" placeholder="Ex: 50.00">
            <small *ngIf="isDecrease">Para redução, informe valor negativo (ex: -50.00)</small>
          </div>

          <!-- Fields for Health Beneficiary -->
          <div *ngIf="isBeneficiaryType" formGroupName="beneficiary">
            <h4>Dados do Beneficiário</h4>
            <div class="form-group">
              <label>Nome Completo</label>
              <input formControlName="name" class="form-control">
            </div>
            <div class="form-group">
              <label>CPF</label>
              <input formControlName="cpf" class="form-control">
            </div>
          </div>

          <div class="form-group">
            <label>Descrição / Motivo</label>
            <textarea formControlName="description" class="form-control" rows="3"></textarea>
          </div>

          <div class="modal-actions">
            <button type="button" (click)="cancel.emit()" [disabled]="isProcessing">Cancelar</button>
            <button type="submit" class="btn-primary" [disabled]="form.invalid || isProcessing">
              {{ isProcessing ? 'Processando...' : 'Confirmar' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 500px; max-width: 90%; }
    .form-group { margin-bottom: 15px; }
    .form-control { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .btn-primary:disabled { background: #ccc; }
    h4 { margin-top: 10px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
  `]
})
export class EndorsementModalComponent implements OnInit {
  @Input() policyId!: number;
  @Input() isHealth = false;
  @Output() confirm = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();

  form: FormGroup;
  isProcessing = false;

  constructor(private fb: FormBuilder, private policyService: PolicyService) {
    this.form = this.fb.group({
      endorsement_type: ['PREMIUM_INCREASE', Validators.required],
      effective_date: [new Date().toISOString().split('T')[0], Validators.required],
      premium_delta: [0],
      description: ['', Validators.required],
      beneficiary: this.fb.group({
        name: [''],
        cpf: ['']
      })
    });
  }

  ngOnInit() { this.onTypeChange(); }

  get showPremiumField(): boolean { return ['PREMIUM_INCREASE', 'PREMIUM_DECREASE', 'HEALTH_ADD_BENEFICIARY'].includes(this.form.get('endorsement_type')?.value); }
  get isBeneficiaryType(): boolean { return this.form.get('endorsement_type')?.value === 'HEALTH_ADD_BENEFICIARY'; }
  get isDecrease(): boolean { return this.form.get('endorsement_type')?.value === 'PREMIUM_DECREASE'; }

  onTypeChange() {
    const type = this.form.get('endorsement_type')?.value;
    const deltaControl = this.form.get('premium_delta');
    const benGroup = this.form.get('beneficiary');

    if (['PREMIUM_INCREASE', 'PREMIUM_DECREASE', 'HEALTH_ADD_BENEFICIARY'].includes(type)) {
      deltaControl?.setValidators([Validators.required]);
    } else {
      deltaControl?.clearValidators();
      deltaControl?.setValue(0);
    }
    deltaControl?.updateValueAndValidity();

    if (type === 'HEALTH_ADD_BENEFICIARY') {
      benGroup?.get('name')?.setValidators(Validators.required);
      benGroup?.get('cpf')?.setValidators(Validators.required);
    } else {
      benGroup?.get('name')?.clearValidators();
      benGroup?.get('cpf')?.clearValidators();
    }
    benGroup?.updateValueAndValidity();
  }

  onSubmit() {
    if (this.form.invalid) return;
    this.isProcessing = true;
    const val = this.form.value;
    
    if (val.endorsement_type === 'CANCELLATION_ENDORSEMENT') {
      this.policyService.cancel(this.policyId, { effective_date: val.effective_date, reason: val.description })
        .pipe(finalize(() => this.isProcessing = false))
        .subscribe({ next: () => this.confirm.emit(), error: (e) => alert(e.message) });
    } else {
      let desc = val.description;
      if (val.endorsement_type === 'HEALTH_ADD_BENEFICIARY') desc += `\nBeneficiário: ${val.beneficiary.name} (CPF: ${val.beneficiary.cpf})`;
      
      this.policyService.applyEndorsement(this.policyId, {
        endorsement_type: val.endorsement_type,
        effective_date: val.effective_date,
        premium_delta: val.premium_delta,
        description: desc
      }).pipe(finalize(() => this.isProcessing = false))
        .subscribe({ next: () => this.confirm.emit(), error: (e) => alert(e.message) });
    }
  }
}