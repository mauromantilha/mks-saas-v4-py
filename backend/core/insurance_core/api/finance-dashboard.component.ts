import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { FinanceService, CashFlowData } from '../finance.service';

@Component({
  selector: 'app-finance-dashboard',
  template: `
    <div class="dashboard-container">
      <h2>Dashboard Financeiro</h2>
      
      <app-finance-alerts></app-finance-alerts>

      <div class="summary-cards" *ngIf="data$ | async as data">
        <div class="card income">
          <h3>Receitas (Período)</h3>
          <p>{{ getTotal(data, 'income') | currency:'BRL' }}</p>
        </div>
        <div class="card expense">
          <h3>Despesas (Período)</h3>
          <p>{{ getTotal(data, 'expense') | currency:'BRL' }}</p>
        </div>
        <div class="card balance">
          <h3>Saldo Líquido</h3>
          <p>{{ getTotal(data, 'balance') | currency:'BRL' }}</p>
        </div>
      </div>

      <div class="chart-container" *ngIf="data$ | async as data">
        <h3>Fluxo de Caixa (Últimos 6 meses)</h3>
        <div class="chart">
          <div *ngFor="let item of data" class="bar-group">
            <div class="bars">
              <div class="bar income" 
                   [style.height.%]="getPercent(item.income, getMax(data))" 
                   [title]="'Receita: ' + (item.income | currency:'BRL')"></div>
              <div class="bar expense" 
                   [style.height.%]="getPercent(item.expense, getMax(data))" 
                   [title]="'Despesa: ' + (item.expense | currency:'BRL')"></div>
            </div>
            <div class="label">{{ item.period }}</div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-container { padding: 20px; }
    .summary-cards { display: flex; gap: 20px; margin-bottom: 30px; }
    .card { flex: 1; padding: 20px; border-radius: 8px; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .card.income { background: #28a745; }
    .card.expense { background: #dc3545; }
    .card.balance { background: #007bff; }
    .card h3 { margin: 0 0 10px 0; font-size: 1rem; opacity: 0.9; }
    .card p { margin: 0; font-size: 1.5rem; font-weight: bold; }
    
    .chart-container { background: white; padding: 20px; border-radius: 8px; border: 1px solid #eee; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .chart { display: flex; justify-content: space-around; align-items: flex-end; height: 300px; padding-top: 20px; }
    .bar-group { display: flex; flex-direction: column; align-items: center; height: 100%; width: 100%; }
    .bars { display: flex; align-items: flex-end; gap: 5px; height: 90%; width: 60%; justify-content: center; border-bottom: 1px solid #ddd; }
    .bar { width: 20px; transition: height 0.3s; border-radius: 4px 4px 0 0; min-height: 1px; }
    .bar.income { background: #28a745; opacity: 0.8; }
    .bar.expense { background: #dc3545; opacity: 0.8; }
    .label { margin-top: 10px; font-size: 0.85em; color: #666; }
  `]
})
export class FinanceDashboardComponent implements OnInit {
  data$: Observable<CashFlowData[]>;

  constructor(private financeService: FinanceService) {}

  ngOnInit() {
    this.data$ = this.financeService.getCashFlow();
  }

  getTotal(data: CashFlowData[], field: keyof CashFlowData): number {
    return data.reduce((acc, item) => acc + (item[field] as number), 0);
  }

  getMax(data: CashFlowData[]): number {
    return Math.max(...data.map(d => Math.max(d.income, d.expense)));
  }

  getPercent(value: number, max: number): number {
    return max > 0 ? (value / max) * 100 : 0;
  }
}