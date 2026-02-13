import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { RouterLink } from "@angular/router";
import { catchError, forkJoin, map, of } from "rxjs";

import { PlanDto, TenantDto } from "../../data-access/control-panel/control-panel.dto";
import { MonitoringApi } from "../../data-access/control-panel/monitoring-api.service";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { normalizeListResponse } from "../../shared/api/response-normalizers";

type DashboardSafeStats = {
  tenants: number;
  activeTenants: number;
  plans: number;
  monitoringServices: number;
  monitoringTenants: number;
  cloudRunStatus: string;
  databaseStatus: string;
  storageStatus: string;
  requestTraffic: number;
  loggedInUsers: number;
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
        <article class="card">
          <span>Cloud Run</span>
          <strong>{{ stats().cloudRunStatus }}</strong>
        </article>
        <article class="card">
          <span>Database</span>
          <strong>{{ stats().databaseStatus }}</strong>
        </article>
        <article class="card">
          <span>Storage</span>
          <strong>{{ stats().storageStatus }}</strong>
        </article>
        <article class="card">
          <span>Tráfego (req/s)</span>
          <strong>{{ stats().requestTraffic }}</strong>
        </article>
        <article class="card">
          <span>Usuários logados</span>
          <strong>{{ stats().loggedInUsers }}</strong>
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

      <section class="tables" *ngIf="!loading()">
        <article class="card">
          <h3>Planos cadastrados</h3>
          <div *ngIf="plans().length === 0">Nenhum plano retornado.</div>
          <table *ngIf="plans().length > 0">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Tier</th>
                <th>Mensal</th>
                <th>Instalação</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let plan of plans()">
                <td>{{ plan.name }}</td>
                <td>{{ plan.tier }}</td>
                <td>{{ plan.price?.monthly_price || "-" }}</td>
                <td>{{ plan.price?.setup_fee || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="card">
          <h3>Tenants recentes</h3>
          <div *ngIf="tenantsPreview().length === 0">Nenhum tenant retornado.</div>
          <table *ngIf="tenantsPreview().length > 0">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Slug</th>
                <th>Status</th>
                <th>Plano</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let tenant of tenantsPreview()">
                <td>{{ tenant.legal_name }}</td>
                <td>{{ tenant.slug }}</td>
                <td>{{ tenant.status }}</td>
                <td>{{ tenant.plan_name || tenant.subscription?.plan?.name || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>
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

      .tables {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 0.8rem;
      }

      table {
        width: 100%;
        border-collapse: collapse;
      }

      th,
      td {
        text-align: left;
        padding: 0.45rem 0.25rem;
        border-bottom: 1px solid var(--mks-border);
        font-size: 0.92rem;
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
    cloudRunStatus: "-",
    databaseStatus: "-",
    storageStatus: "-",
    requestTraffic: 0,
    loggedInUsers: 0,
  });
  readonly plans = signal<PlanDto[]>([]);
  readonly tenantsPreview = signal<TenantDto[]>([]);

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
      preview: this.tenantApi
        .listTenants({ page: 1, page_size: 8 })
        .pipe(catchError(() => of({ items: [] as TenantDto[], total: 0, page: 1, page_size: 8 }))),
      plans: this.plansApi.listPlans().pipe(catchError(() => of([]))),
      monitoring: this.monitoringApi
        .getGlobalHealth({ period: "24h", page_size: 20 })
        .pipe(catchError(() => of(null))),
    })
      .pipe(
        map((data) => {
          const normalizedPlans = normalizeListResponse<PlanDto>(data.plans);
          return {
            tenants: data.tenants?.total ?? 0,
            activeTenants: data.activeTenants?.total ?? 0,
            plans: normalizedPlans.count ?? 0,
            monitoringServices: Array.isArray(data.monitoring?.services) ? data.monitoring.services.length : 0,
            monitoringTenants: Array.isArray(data.monitoring?.tenants) ? data.monitoring.tenants.length : 0,
            cloudRunStatus: data.monitoring?.summary?.cloud_run_status || "-",
            databaseStatus: data.monitoring?.summary?.database_status || "-",
            storageStatus: data.monitoring?.summary?.storage_status || "-",
            requestTraffic: data.monitoring?.summary?.request_traffic ?? 0,
            loggedInUsers: data.monitoring?.summary?.logged_in_users ?? 0,
            plansList: normalizedPlans.results,
            tenantsPreview: data.preview?.items || [],
          };
        })
      )
      .subscribe({
        next: (stats) => {
          this.stats.set({
            tenants: stats.tenants,
            activeTenants: stats.activeTenants,
            plans: stats.plans,
            monitoringServices: stats.monitoringServices,
            monitoringTenants: stats.monitoringTenants,
            cloudRunStatus: stats.cloudRunStatus,
            databaseStatus: stats.databaseStatus,
            storageStatus: stats.storageStatus,
            requestTraffic: stats.requestTraffic,
            loggedInUsers: stats.loggedInUsers,
          });
          this.plans.set(stats.plansList);
          this.tenantsPreview.set(stats.tenantsPreview);
          this.loading.set(false);
        },
        error: () => {
          this.error.set("Falha ao carregar dados do dashboard.");
          this.loading.set(false);
        },
      });
  }
}
