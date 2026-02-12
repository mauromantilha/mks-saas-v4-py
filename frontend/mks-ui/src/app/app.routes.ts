import { Routes } from "@angular/router";

import { authGuard } from "./core/auth/auth.guard";
import { permissionGuard } from "./core/auth/permission.guard";
import { portalGuard } from "./core/portal/portal.guard";
import { ForgotPasswordPageComponent } from "./features/auth/forgot-password-page.component";
import { LoginPageComponent } from "./features/auth/login-page.component";
import { ResetPasswordPageComponent } from "./features/auth/reset-password-page.component";
import { PlatformTenantsPageComponent } from "./features/platform/platform-tenants-page.component";
import { PlatformMonitoringPageComponent } from "./features/platform/platform-monitoring-page.component";
import { PlatformTenantMonitoringPageComponent } from "./features/platform/platform-tenant-monitoring-page.component";
import { SalesFlowPageComponent } from "./features/sales/sales-flow-page.component";
import { SectionPlaceholderPageComponent } from "./features/shared/section-placeholder-page.component";
import { TenantActivitiesPageComponent } from "./features/tenant/tenant-activities-page.component";
import { TenantAIAssistantPageComponent } from "./features/tenant/tenant-ai-assistant-page.component";
import { TenantCustomersPageComponent } from "./features/tenant/tenant-customers-page.component";
import { TenantDashboardPageComponent } from "./features/tenant/tenant-dashboard-page.component";
import { TenantInsurersPageComponent } from "./features/tenant/tenant-insurers-page.component";
import { TenantLeadsPageComponent } from "./features/tenant/tenant-leads-page.component";
import { TenantOpportunitiesPageComponent } from "./features/tenant/tenant-opportunities-page.component";
import { TenantFinancePageComponent } from "./features/tenant/tenant-finance-page.component";
import { TenantPoliciesPageComponent } from "./features/tenant/tenant-policies-page.component";
import { TenantPolicyRequestsPageComponent } from "./features/tenant/tenant-policy-requests-page.component";
import { TenantProposalOptionsPageComponent } from "./features/tenant/tenant-proposal-options-page.component";
import { TenantSpecialProjectsPageComponent } from "./features/tenant/tenant-special-projects-page.component";
import { TenantMembersPageComponent } from "./features/tenant-settings/tenant-members-page.component";
import { TenantFiscalPageComponent } from "./features/tenant-settings/tenant-fiscal-page.component";
import { TenantLedgerPageComponent } from "./features/tenant-settings/tenant-ledger-page.component";
import { TenantRbacPageComponent } from "./features/tenant-settings/tenant-rbac-page.component";

export const routes: Routes = [
  { path: "", pathMatch: "full", redirectTo: "login" },
  { path: "login", component: LoginPageComponent },
  { path: "forgot-password", component: ForgotPasswordPageComponent },
  { path: "reset-password", component: ResetPasswordPageComponent },
  {
    path: "sales/flow",
    component: SalesFlowPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "TENANT" },
  },
  {
    path: "tenant/dashboard",
    component: TenantDashboardPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Painel do Tenant",
      description:
        "Resumo operacional do tenant: funil, emissão, renovação e alertas.",
    },
  },
  {
    path: "tenant/customers",
    component: TenantCustomersPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Clientes",
      description:
        "Cadastro completo de clientes e histórico comercial consolidado.",
    },
  },
  {
    path: "tenant/leads",
    component: TenantLeadsPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Leads",
      description:
        "Entrada de leads por webhook/API/importação, com enriquecimento por IA.",
    },
  },
  {
    path: "tenant/opportunities",
    component: TenantOpportunitiesPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Oportunidades",
      description:
        "Gestão detalhada do pipeline comercial com etapas e KPIs de conversão.",
    },
  },
  {
    path: "tenant/activities",
    component: TenantActivitiesPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Atividades e Follow-up",
      description:
        "Tarefas comerciais com SLA, lembretes e histórico por lead/oportunidade.",
    },
  },
  {
    path: "tenant/ai-assistant",
    component: TenantAIAssistantPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "IA Assistente",
      description:
        "Consultoria comercial e de seguros com IA, contexto do tenant e memória de aprendizado.",
    },
  },
  {
    path: "tenant/radar-leads",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Radar de Leads",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/special-projects",
    component: TenantSpecialProjectsPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Projetos Especiais",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/goals",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Metas",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/manager-view",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Visão Gestor",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/messaging",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Mensageria",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/insurers",
    component: TenantInsurersPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Seguradoras",
      description:
        "Cadastro e gestão de seguradoras (insurers) com regras de integração por tenant.",
    },
  },
  {
    path: "tenant/finance",
    component: TenantFinancePageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Financeiro",
      description:
        "Recebíveis, parcelas e inadimplência do tenant com integração ao operacional.",
    },
  },
  {
    path: "tenant/commissions-flow",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Comissões/Fluxo",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/installments-clients",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Parcelas (Clientes)",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/accounts-payable",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Contas a Pagar",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/bank-reconciliation",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Conciliação Bancos (OFX)",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/commission-closing",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Fechamento Comissão",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/policies",
    component: TenantPoliciesPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Apólices",
      description:
        "Gestão operacional de apólices, itens segurados, coberturas, documentos e endossos.",
    },
  },
  {
    path: "tenant/policy-requests",
    component: TenantPolicyRequestsPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Pedidos de Emissão",
      description:
        "Handover de venda para emissão com vistoria e dados de cobrança.",
    },
  },
  {
    path: "tenant/proposal-options",
    component: TenantProposalOptionsPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Propostas Comparativas",
      description:
        "Comparativo de seguradoras, plano recomendado e estratégia comercial.",
    },
  },
  {
    path: "tenant/documents",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Documentos",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/import-customers",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Importar Clientes",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/system-monitor",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Sistema/Monitor",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "control-panel",
    canActivate: [authGuard, portalGuard, permissionGuard],
    data: { portal: "CONTROL_PLANE", permission: "control_panel.access" },
    loadChildren: () =>
      import("./features/control-panel/control-panel.module").then(
        (m) => m.ControlPanelModule
      ),
  },
  // Legacy routes kept for backward compatibility while migrating to /control-panel/*.
  {
    path: "platform/tenants",
    component: PlatformTenantsPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "CONTROL_PLANE" },
  },
  {
    path: "platform/contracts",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "CONTROL_PLANE",
      title: "Control Plane: Contratos",
      description:
        "Gestão de contrato, plano, assentos, vigência e cobrança de tenants.",
    },
  },
  {
    path: "platform/monitoring",
    component: PlatformMonitoringPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "CONTROL_PLANE",
      title: "Control Plane: Monitoramento",
      description:
        "Saúde de provisionamento, banco por tenant e telemetria operacional.",
    },
  },
  {
    path: "platform/tenants/:id/monitoring",
    component: PlatformTenantMonitoringPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "CONTROL_PLANE" },
  },
  {
    path: "tenant/members",
    component: TenantMembersPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "TENANT" },
  },
  {
    path: "tenant/ledger",
    component: TenantLedgerPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "TENANT" },
  },
  {
    path: "tenant/fiscal",
    component: TenantFiscalPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Fiscal (NF)",
      description: "Emissão, cancelamento e auditoria de documentos fiscais do tenant.",
    },
  },
  {
    path: "tenant/fiscal-settings",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Fiscal",
      description: "Módulo em desenvolvimento.",
    },
  },
  {
    path: "tenant/rbac",
    component: TenantRbacPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "TENANT" },
  },
  { path: "**", redirectTo: "login" },
];
