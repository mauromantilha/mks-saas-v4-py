import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { FinanceService, FinanceAlert } from './finance.service';

@Component({
  selector: 'app-finance-alerts',
  template: `
    <div class="alerts-container" *ngIf="alerts$ | async as alerts">
      <div *ngFor="let alert of alerts" class="alert-card" [ngClass]="alert.type.toLowerCase()">
        <div class="icon">
          {{ alert.type === 'OVERDUE' ? '⚠️' : '📅' }}
        </div>
        <div class="content">
          <h4>{{ getTitle(alert.type) }}</h4>
          <p>
            <strong>{{ alert.count }}</strong> parcelas 
            <span class="amount">({{ alert.amount | currency:'BRL' }})</span>
          </p>
        </div>
        <div class="action">
          <button class="btn-link">Ver Lista</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .alerts-container { display: flex; flex-direction: column; gap: 15px; margin-bottom: 20px; }
    .alert-card { 
      display: flex; align-items: center; padding: 15px; border-radius: 8px; 
      border-left: 5px solid; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .alert-card.overdue { border-left-color: #dc3545; background: #fff5f5; }
    .alert-card.due_soon { border-left-color: #ffc107; background: #fffbf0; }
    
    .icon { font-size: 1.5rem; margin-right: 15px; }
    .content { flex: 1; }
    .content h4 { margin: 0 0 5px 0; font-size: 1rem; color: #333; }
    .content p { margin: 0; color: #666; font-size: 0.9rem; }
    .amount { font-weight: bold; color: #333; }
    
    .action { margin-left: 15px; }
    .btn-link { 
      background: none; border: none; color: #007bff; 
      cursor: pointer; text-decoration: underline; font-size: 0.9rem; 
    }
  `]
})
export class FinanceAlertsComponent implements OnInit {
  alerts$: Observable<FinanceAlert[]>;

  constructor(private financeService: FinanceService) {}

  ngOnInit() {
    this.alerts$ = this.financeService.getAlerts();
  }

  getTitle(type: string): string {
    return type === 'OVERDUE' 
      ? 'Pagamentos em Atraso' 
      : 'A Vencer (Próximos 7 dias)';
  }
}