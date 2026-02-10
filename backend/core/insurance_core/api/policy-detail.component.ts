import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import { Policy, PolicyService } from '../policy.service';
import { PermissionService } from '../core/services/permission.service';

@Component({
  selector: 'app-policy-detail',
  template: `
    <div class="detail-container" *ngIf="policy$ | async as policy">
      <div class="header">
        <div class="title-section">
          <h1>Apólice {{ policy.policy_number }}</h1>
          <span class="badge" [ngClass]="'badge-' + policy.status.toLowerCase()">{{ policy.status }}</span>
        </div>
        
        <div class="actions">
          <ng-container *appHasPermission="'policy.issue'">
            <button *ngIf="policy.status === 'QUOTED'" 
                    (click)="issuePolicy(policy)" 
                    class="btn-primary"
                    [disabled]="isProcessing">
              {{ isProcessing ? 'Emitindo...' : 'Emitir Apólice' }}
            </button>
          </ng-container>
        </div>
      </div>

      <nav class="tabs">
        <a routerLink="overview" routerLinkActive="active">Visão Geral</a>
        <a routerLink="billing" routerLinkActive="active">Financeiro</a>
        <a routerLink="endorsements" routerLinkActive="active">Endossos</a>
        <a routerLink="claims" routerLinkActive="active">Sinistros</a>
        <a routerLink="documents" routerLinkActive="active">Documentos</a>
        <a routerLink="audit" routerLinkActive="active">Auditoria</a>
      </nav>

      <div class="content-area">
        <router-outlet></router-outlet>
      </div>
    </div>
  `,
  styles: [`
    .detail-container { padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .title-section { display: flex; align-items: center; gap: 15px; }
    .badge { padding: 5px 10px; border-radius: 15px; font-size: 0.9em; font-weight: bold; }
    .badge-quoted { background: #e3f2fd; color: #0d47a1; }
    .badge-issued, .badge-active { background: #e8f5e9; color: #1b5e20; }
    .badge-cancelled { background: #ffebee; color: #b71c1c; }
    
    .tabs { display: flex; border-bottom: 1px solid #ddd; margin-bottom: 20px; }
    .tabs a { 
      padding: 10px 20px; 
      text-decoration: none; 
      color: #666; 
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .tabs a:hover { background: #f9f9f9; }
    .tabs a.active { border-bottom-color: #007bff; color: #007bff; font-weight: 500; }
    
    .btn-primary { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .btn-primary:disabled { background: #ccc; cursor: not-allowed; }
  `]
})
export class PolicyDetailComponent implements OnInit {
  policy$: Observable<Policy>;
  isProcessing = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private policyService: PolicyService,
    private permissionService: PermissionService
  ) {}

  ngOnInit(): void {
    this.policy$ = this.route.data.pipe(map(data => data['policy']));
  }

  issuePolicy(policy: Policy): void {
    if (!confirm(`Confirma a emissão da apólice ${policy.policy_number}?`)) return;
    
    this.isProcessing = true;
    this.policyService.issue(policy.id).subscribe(() => {
      this.isProcessing = false;
      // Recarrega a rota ou navega para billing conforme solicitado
      this.router.navigate(['billing'], { relativeTo: this.route }).then(() => {
        // Força reload do resolver se necessário, ou atualiza localmente.
        // Como navegamos para child, o parent component não é destruído, 
        // mas o resolver roda na mudança de params se configurado.
        // Aqui, simplificamos assumindo que o usuário verá o status atualizado se recarregar,
        // ou poderíamos atualizar o Observable localmente.
        window.location.reload(); // Maneira simples de garantir estado fresco após ação crítica
      });
    this.policyService.issue(policy.id).subscribe({
      next: () => {
        this.isProcessing = false;
        // Navega para a aba financeiro sem recarregar a página inteira
        this.router.navigate(['billing'], { relativeTo: this.route });
      },
      error: (err) => {
        this.isProcessing = false;
        console.error('Erro ao emitir apólice:', err);
        // Idealmente, chamar um ToastService aqui
      }
    });
  }
}