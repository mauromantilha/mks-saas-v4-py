import { Component, OnInit } from '@angular/core';
import { FinanceService, BankTransaction, Installment } from '../finance.service';
import { Observable, BehaviorSubject } from 'rxjs';
import { switchMap, finalize } from 'rxjs/operators';

@Component({
  selector: 'app-banking',
  template: `
    <div class="banking-container">
      <div class="header">
        <h2>Conciliação Bancária</h2>
        <div class="actions">
          <input #fileInput type="file" (change)="importOfx($event)" accept=".ofx" style="display:none">
          <button (click)="fileInput.click()" class="btn-primary" [disabled]="isUploading">
            {{ isUploading ? 'Enviando...' : 'Importar OFX' }}
          </button>
        </div>
      </div>
      <p class="subtitle">Transações pendentes de conciliação</p>

      <table class="table" *ngIf="transactions$ | async as transactions">
        <thead>
          <tr>
            <th>Data</th>
            <th>Descrição</th>
            <th>Valor</th>
            <th>ID Externo</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let tx of transactions">
            <td>{{ tx.date | date:'dd/MM/yyyy' }}</td>
            <td>{{ tx.description }}</td>
            <td>{{ tx.amount | currency:'BRL' }}</td>
            <td>{{ tx.external_id }}</td>
            <td>
              <button (click)="openMatchModal(tx)" class="btn-sm btn-primary">Conciliar</button>
            </td>
          </tr>
          <tr *ngIf="transactions.length === 0">
            <td colspan="5" class="text-center">Todas as transações estão conciliadas.</td>
          </tr>
        </tbody>
      </table>

      <!-- Simple Match Modal -->
      <div class="modal-backdrop" *ngIf="selectedTransaction">
        <div class="modal-content">
          <h3>Conciliar Transação</h3>
          <div class="tx-info">
            <p><strong>Transação:</strong> {{ selectedTransaction.description }}</p>
            <p><strong>Valor:</strong> {{ selectedTransaction.amount | currency:'BRL' }}</p>
          </div>

          <div class="search-box">
            <label>Buscar Parcela (ID ou Valor)</label>
            <div class="input-group">
              <input #searchInput type="text" placeholder="Buscar..." class="form-control">
              <button (click)="searchInstallments(searchInput.value)">Buscar</button>
            </div>
          </div>

          <div class="candidates-list" *ngIf="candidates.length > 0">
            <table>
              <tr *ngFor="let cand of candidates">
                <td>#{{ cand.id }}</td>
                <td>{{ cand.due_date | date:'dd/MM/yyyy' }}</td>
                <td>{{ cand.amount | currency:'BRL' }}</td>
                <td><button (click)="confirmMatch(cand)" class="btn-sm btn-success">Selecionar</button></td>
              </tr>
            </table>
          </div>

          <div class="modal-actions">
            <button (click)="selectedTransaction = null">Cancelar</button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .banking-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .subtitle { color: #666; margin-bottom: 20px; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    .btn-sm { padding: 4px 8px; font-size: 0.9em; cursor: pointer; border-radius: 4px; border: none; }
    .btn-primary { background: #007bff; color: white; }
    .btn-success { background: #28a745; color: white; }
    
    .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-content { background: white; padding: 20px; border-radius: 8px; width: 500px; max-width: 90%; }
    .tx-info { background: #f8f9fa; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
    .search-box { margin-bottom: 15px; }
    .input-group { display: flex; gap: 10px; margin-top: 5px; }
    .form-control { flex: 1; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
    .candidates-list table { width: 100%; margin-top: 10px; }
    .modal-actions { margin-top: 20px; text-align: right; }
  `]
})
export class BankingComponent implements OnInit {
  transactions$: Observable<BankTransaction[]>;
  refresh$ = new BehaviorSubject<void>(undefined);
  isUploading = false;
  
  selectedTransaction: BankTransaction | null = null;
  candidates: Installment[] = [];

  constructor(private financeService: FinanceService) {}

  ngOnInit() {
    this.transactions$ = this.refresh$.pipe(switchMap(() => this.financeService.listBankTransactions({ status: 'PENDING' })));
  }

  openMatchModal(tx: BankTransaction) { this.selectedTransaction = tx; this.candidates = []; }

  searchInstallments(query: string) {
    // Simple search logic: if query is empty, list open installments around transaction amount?
    // For now, just listing OPEN installments. In real app, would pass query to backend.
    this.financeService.listInstallments({ status: 'OPEN' }).subscribe(res => this.candidates = res);
  }

  confirmMatch(inst: Installment) {
    if (!this.selectedTransaction) return;
    if (confirm(`Confirmar conciliação da transação ${this.selectedTransaction.id} com parcela ${inst.id}?`)) {
      this.financeService.reconcile(this.selectedTransaction.id, inst.id).subscribe(() => {
        this.selectedTransaction = null;
        this.refresh$.next();
      });
    }
  }

  importOfx(event: any) {
    const file = event.target.files[0];
    if (file) {
      this.isUploading = true;
      this.financeService.importOfx(file).pipe(
        finalize(() => this.isUploading = false)
      ).subscribe({
        next: () => {
          alert('Arquivo importado com sucesso!');
          this.refresh$.next();
        },
        error: (err) => alert('Erro ao importar arquivo: ' + (err.message || 'Erro desconhecido'))
      });
    }
    event.target.value = '';
  }
}