import { NgModule } from "@angular/core";
import { RouterModule, Routes } from "@angular/router";

import { permissionGuard } from "../../core/auth/permission.guard";
import { portalGuard } from "../../core/portal/portal.guard";
import { authGuard } from "../../core/auth/auth.guard";
import { ControlPanelAuditPageComponent } from "./control-panel-audit-page.component";
import { ControlPanelContractsPageComponent } from "./control-panel-contracts-page.component";
import { ControlPanelDashboardPageComponent } from "./control-panel-dashboard-page.component";
import { ControlPanelLayoutComponent } from "./control-panel-layout.component";
import { ControlPanelMonitoringGlobalPageComponent } from "./control-panel-monitoring-global-page.component";
import { controlPanelPlansResolver } from "./control-panel-plans.resolver";
import { controlPanelTenantResolver } from "./control-panel-tenant.resolver";
import { ControlPanelCreateTenantPageComponent } from "./control-panel-create-tenant-page.component";
import { ControlPanelEditTenantPageComponent } from "./control-panel-edit-tenant-page.component";
import { ControlPanelPlansPageComponent } from "./control-panel-plans-page.component";
import { ControlPanelTenantDetailShellComponent } from "./control-panel-tenant-detail-shell.component";
import { ControlPanelTenantsListPageComponent } from "./control-panel-tenants-list-page.component";

const routes: Routes = [
  {
    path: "",
    component: ControlPanelLayoutComponent,
    canActivate: [authGuard, portalGuard, permissionGuard],
    data: { portal: "CONTROL_PLANE", permission: "cp.access" },
    children: [
      { path: "", pathMatch: "full", redirectTo: "dashboard" },
      {
        path: "dashboard",
        component: ControlPanelDashboardPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "control_panel.dashboard",
          title: "Dashboard",
          description: "Visão geral do SaaS: tenants ativos, uso e alertas críticos.",
        },
      },
      {
        path: "tenants",
        component: ControlPanelTenantsListPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "cp.tenants.view",
          title: "Tenants",
          description: "Gestão de tenants, planos, status e governança operacional.",
        },
      },
      {
        path: "tenants/new",
        component: ControlPanelCreateTenantPageComponent,
        canActivate: [permissionGuard],
        data: { permission: "cp.tenants.manage" },
      },
      {
        path: "tenants/:id/edit",
        component: ControlPanelEditTenantPageComponent,
        canActivate: [permissionGuard],
        data: { permission: "cp.tenants.manage" },
      },
      {
        path: "tenants/:id",
        component: ControlPanelTenantDetailShellComponent,
        canActivate: [permissionGuard],
        resolve: {
          tenant: controlPanelTenantResolver,
          plans: controlPanelPlansResolver,
        },
        data: { permission: "cp.tenants.view" },
      },
      {
        path: "plans",
        component: ControlPanelPlansPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "cp.plans.view",
          title: "Plans",
          description: "Catálogo de planos, preços e status de disponibilidade.",
        },
      },
      {
        path: "contracts",
        component: ControlPanelContractsPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "control_panel.contracts.read",
          title: "Contracts",
          description: "Acompanhamento de contratos, envio e status de assinatura.",
        },
      },
      {
        path: "monitoring",
        component: ControlPanelMonitoringGlobalPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "cp.monitoring.view",
          title: "Monitoring",
          description: "Monitoramento global e por tenant com telemetria operacional.",
        },
      },
      {
        path: "audit",
        component: ControlPanelAuditPageComponent,
        canActivate: [permissionGuard],
        data: {
          permission: "control_panel.audit.read",
          title: "Audit",
          description: "Auditoria administrativa e trilha de mudanças no control panel.",
        },
      },
    ],
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ControlPanelRoutingModule {}
