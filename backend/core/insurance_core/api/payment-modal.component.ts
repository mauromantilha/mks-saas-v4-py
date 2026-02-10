import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { switchMap, finalize } from 'rxjs/operators';
import { of } from 'rxjs';
import { FinanceService, Installment } from '../finance.service';
import { DocumentService } from '../document.service';

@Component({
  selector: 'app-payment-modal',
  template: `
    <div class="modal-backdrop">
      <div class="modal-content">
        <h3>Registrar Pagamento - Parcela {{ installment.number }}</h3>
        
        <form [formGroup]="form" (ngSubmit)="onSubmit()">
          <div class="form-group">
            <label>Data do Pagamento</label>
            <input type="date" formControlName="payment_date" class="form-control">
          </div>

          <div class="form-group">
            <label>Valor Pago (R$)</label>
            <input type="number" formControlName="amount" class="form-control">
          </div>

          <div class="form-group">
            <label>Método</label>
            <select formControlName="method" class="form-control">
              <option value="BOLETO">Boleto</option>
              <option value="PIX">Pix</option>
              <option value="TRANSFER">Transferência</option>
              <option value="CREDIT_CARD">Cartão de Crédito</option>
            </select>
          </div>

          <div class="form-group">
            <label>Comprovante (Opcional)</label>
            <input type="file" (change)="onFileSelected($event)" class="form-control">
          </div>

          <div class="modal-actions">
            <button type="button" (click)="cancel.emit()" [disabled]="isProcessing">Cancelar</button>
            <button type="submit" class="btn-primary" [disabled]="form.invalid || isProcessing">
              {{ isProcessing ? 'Processando...' : 'Confirmar Pagamento' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 400px; max-width: 90%; }
    .form-group { margin-bottom: 15px; }
    .form-control { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .btn-primary:disabled { background: #ccc; }
  `]
})
export class PaymentModalComponent {
  @Input() installment!: Installment;
  @Input() policyId!: number;
  @Output() confirm = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();

  form: FormGroup;
  selectedFile: File | null = null;
  isProcessing = false;

  constructor(
    private fb: FormBuilder,
    private financeService: FinanceService,
    private documentService: DocumentService,
    private http: HttpClient
  ) {
    this.form = this.fb.group({
      payment_date: [new Date().toISOString().split('T')[0], Validators.required],
      amount: [0, [Validators.required, Validators.min(0.01)]],
      method: ['BOLETO', Validators.required]
    });
  }

  ngOnInit() {
    if (this.installment) {
      this.form.patchValue({ amount: this.installment.amount });
    }
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0] || null;
  }

  onSubmit() {
    if (this.form.invalid) return;
    this.isProcessing = true;

    const paymentData = this.form.value;

    this.financeService.registerPayment(this.installment.id, paymentData).pipe(
      switchMap(() => {
        if (!this.selectedFile) return of(null);

        return this.documentService.getSignedUploadUrl({
          entity_type: 'POLICY',
          entity_id: this.policyId,
          file_name: this.selectedFile.name,
          content_type: this.selectedFile.type,
          file_size: this.selectedFile.size,
          document_type: 'BILL'
        }).pipe(
          switchMap(res => this.http.put(res.upload_url, this.selectedFile, { headers: { 'Content-Type': this.selectedFile!.type } }).pipe(
            switchMap(() => this.documentService.confirmUpload(res.document_id))
          ))
        );
      }),
      finalize(() => this.isProcessing = false)
    ).subscribe({
      next: () => this.confirm.emit(),
      error: (err) => alert('Erro ao registrar pagamento: ' + (err.message || 'Erro desconhecido'))
    });
  }
}