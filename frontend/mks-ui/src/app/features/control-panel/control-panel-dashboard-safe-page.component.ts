import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { RouterLink } from "@angular/router";
import { catchError, forkJoin, map, of } from "rxjs";

import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";

type DashboardSafeStats = {
  tenants: number;
  activeTenants: number;
  plans: number;
  monitoringServices: number;
  monitoringTenants: number;
};

@Component({
  selector: "app-control-panel-dashboard-safe-page",
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="safe-dashboard">
      <header>
        <h1>Dashboard</h1>
        <p>Modo estável do Control Panel (fallback seguro).</p>
      </header>

      <div class="alerts" *ngIf="error()">
        {{ error() }}
      </div>

      <div class="stats" *ngIf="!loading(); else loadingTpl">
        <article class="card">
          <span>Tenants</span>
          <strong>{{ stats().tenants }}</strong>
        </article>
        <article class="card">
          <span>Tenants ativos</span>
          <strong>{{ stats().activeTenants }}</strong>
        </article>
        <article class="card">
          <span>Planos</span>
          <strong>{{ stats().plans }}</strong>
        </article>
        <article class="card">
          <span>Serviços monitorados</span>
          <strong>{{ stats().monitoringServices }}</strong>
        </article>
        <article class="card">
          <span>Tenants monitorados</span>
          <strong>{{ stats().monitoringTenants }}</strong>
        </article>
      </div>

      <ng-template #loadingTpl>
        <p>Carregando dashboard...</p>
      </ng-template>

      <nav class="quick-links">
        <a routerLink="/control-panel/tenants">Ir para Tenants</a>
        <a routerLink="/control-panel/plans">Ir para Plans</a>
        <a routerLink="/control-panel/contracts">Ir para Contracts</a>
        <a routerLink="/control-panel/monitoring">Ir para Monitoring</a>
        <a routerLink="/control-panel/audit">Ir para Audit</a>
      </nav>
    </section>
  `,
  styles: [
    `
      .safe-dashboard {
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }

      .alerts {
        border: 1px solid #f59e0b;
        background: #fffbeb;
        color: #92400e;
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
      }

      .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
      }

      .card {
        border: 1px solid var(--mks-border);
        background: var(--mks-surface);
        border-radius: 10px;
        padding: 0.8rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }

      .card span {
        color: var(--mks-muted);
      }

      .card strong {
        font-size: 1.4rem;
      }

      .quick-links {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
      }

      .quick-links a {
        text-decoration: none;
        padding: 0.55rem 0.75rem;
        border: 1px solid var(--mks-border);
        border-radius: 9px;
        color: var(--mks-text);
        background: var(--mks-surface);
      }
    `,
  ],
})
export class ControlPanelDashboardSafePageComponent implements OnInit {
  readonly loading = signal(false);
  readonly error = signal("");
  readonly stats = signal<DashboardSafeStats>({
    tenants: 0,
    activeTenants: 0,
    plans: 0,
    monitoringServices: 0,
    monitoringTenants: 0,
  });

  constructor(
    private readonly tenantApi: TenantApi,
    private readonly plansApi: PlansApi,
    private readonly monitoringApi: MonitoringApi
  ) {}

  ngOnInit(): void {
    this.loading.set(true);
    this.error.set("");
    forkJoin({
      tenants: this.tenantApi.listTenants({ page: 1, page_size: 1 }).pipe(catchError(() => of(null))),
      activeTenants: this.tenantApi
        .listTenants({ status: "ACTIVE", page: 1, page_size: 1 })
        .pipe(catchError(() => of(null))),
      plans: this.plansApi.listPlans().pipe(catchError(() => of([]))),
      monitoring: this.monitoringApi
        .getGlobalHealth({ period: "24h", page_size: 20 })
        .pipe(catchError(() => of(null))),
    })
      .pipe(map((data) => ({
        tenants: data.tenants?.total ?? 0,
        activeTenants: data.activeTenants?.total ?? 0,
        plans: Array.isArray(data.plans) ? data.plans.length : 0,
        monitoringServices: Array.isArray(data.monitoring?.services) ? data.monitoring.services.length : 0,
        monitoringTenants: Array.isArray(data.monitoring?.tenants) ? data.monitoring.tenants.length : 0,
      })))
      .subscribe({
        next: (stats) => {
          this.stats.set(stats);
          this.loading.set(false);
        },
        error: () => {
          this.error.set("Falha ao carregar dados do dashboard.");
          this.loading.set(false);
        },
      });
  }
}

