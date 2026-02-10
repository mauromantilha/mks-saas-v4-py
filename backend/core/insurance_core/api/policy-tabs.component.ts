import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Policy } from '../policy.service';

@Component({
  template: `
    <div class="tab-content" *ngIf="policy$ | async as policy">
      <h3>Visão Geral</h3>
      <div class="grid">
        <div><strong>Segurado:</strong> {{ policy.customer.name }}</div>
        <div><strong>Produto:</strong> {{ policy.product.name }}</div>
        <div><strong>Vigência:</strong> {{ policy.start_date | date:'dd/MM/yyyy' }} a {{ policy.end_date | date:'dd/MM/yyyy' }}</div>
        <div><strong>Status:</strong> {{ policy.status }}</div>
      </div>
    </div>
  `,
  styles: ['.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }']
})
export class PolicyOverviewComponent implements OnInit {
  policy$: Observable<Policy>;
  constructor(private route: ActivatedRoute) {}
  ngOnInit() { this.policy$ = this.route.parent!.data.pipe(map(d => d.policy)); }
}

@Component({ template: '<h3>Financeiro / Cobrança</h3><p>Lista de parcelas e faturas aqui.</p>' })
export class PolicyBillingComponent {}

@Component({ template: '<h3>Endossos</h3><p>Histórico de alterações da apólice.</p>' })
export class PolicyEndorsementsComponent {}

@Component({ template: '<h3>Sinistros</h3><p>Lista de sinistros vinculados.</p>' })
export class PolicyClaimsComponent {}

@Component({ template: '<h3>Documentos</h3><p>Arquivos e apólices assinadas.</p>' })
export class PolicyDocumentsComponent {}

@Component({ template: '<h3>Auditoria</h3><p>Log de alterações (Audit Trail).</p>' })
export class PolicyAuditComponent {}