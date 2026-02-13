import { Route, Routes } from "@angular/router";

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

const tenantGuards = [authGuard, portalGuard];

function tenantRoute(
  path: string,
  component: Route["component"],
  title: string,
  description: string,
  permission?: string
): Route {
  return {
    path,
    component,
    canActivate: permission ? [...tenantGuards, permissionGuard] : tenantGuards,
    data: {
      portal: "TENANT",
      title,
      description,
      ...(permission ? { permission } : {}),
    },
  };
}

function tenantPlaceholderRoute(path: string, title: string): Route {
  return tenantRoute(
    path,
    SectionPlaceholderPageComponent,
    title,
    "Funcionalidade em evolução contínua."
  );
}

function aliasRoute(path: string, redirectTo: string): Route {
  return {
    path,
    pathMatch: "full",
    redirectTo,
  };
}

const tenantCanonicalRoutes: Route[] = [
  tenantRoute(
    "tenant/dashboard",
    TenantDashboardPageComponent,
    "Painel do Tenant",
    "Resumo operacional do tenant: funil, emissão, renovação e alertas.",
    "tenant.dashboard.view"
  ),
  tenantRoute(
    "tenant/comercial/ai-assistente",
    TenantAIAssistantPageComponent,
    "IA Assistente",
    "Consultoria comercial e de seguros com IA, contexto do tenant e memória de aprendizado.",
    "tenant.ai_assistant.view"
  ),
  tenantRoute(
    "tenant/comercial/fluxo",
    SalesFlowPageComponent,
    "Fluxo Comercial",
    "Pipeline comercial por etapa, com conversão e handover para emissão."
  ),
  tenantRoute(
    "tenant/comercial/leads",
    TenantLeadsPageComponent,
    "Leads/Funil",
    "Entrada de leads por webhook/API/importação, com enriquecimento por IA.",
    "tenant.leads.view"
  ),
  tenantRoute(
    "tenant/comercial/radar-leads",
    SectionPlaceholderPageComponent,
    "Radar de Leads",
    "Funcionalidade em evolução contínua."
  ),
  tenantRoute(
    "tenant/comercial/projetos-especiais",
    TenantSpecialProjectsPageComponent,
    "Projetos Especiais",
    "Funcionalidade em evolução contínua."
  ),
  tenantRoute(
    "tenant/comercial/clientes",
    TenantCustomersPageComponent,
    "Clientes",
    "Cadastro completo de clientes e histórico comercial consolidado.",
    "tenant.customers.view"
  ),
  tenantRoute(
    "tenant/comercial/oportunidades",
    TenantOpportunitiesPageComponent,
    "Oportunidades",
    "Gestão detalhada do pipeline comercial com etapas e KPIs de conversão.",
    "tenant.opportunities.view"
  ),
  tenantPlaceholderRoute("tenant/comercial/metas", "Metas"),
  tenantPlaceholderRoute("tenant/comercial/visao-gestor", "Visão Gestor"),
  tenantPlaceholderRoute("tenant/comercial/mensageria", "Mensageria"),
  tenantRoute(
    "tenant/comercial/atividades",
    TenantActivitiesPageComponent,
    "Atividade/Agenda",
    "Tarefas comerciais com SLA, lembretes e histórico por lead/oportunidade.",
    "tenant.activities.view"
  ),
  tenantRoute(
    "tenant/operacional/apolices",
    TenantPoliciesPageComponent,
    "Apólices",
    "Gestão operacional de apólices, itens segurados, coberturas, documentos e endossos.",
    "tenant.apolices.view"
  ),
  tenantRoute(
    "tenant/operacional/seguradoras",
    TenantInsurersPageComponent,
    "Seguradoras",
    "Cadastro e gestão de seguradoras (insurers) com regras de integração por tenant.",
    "tenant.insurers.view"
  ),
  tenantRoute(
    "tenant/operacional/propostas",
    TenantProposalOptionsPageComponent,
    "Propostas",
    "Comparativo de seguradoras, plano recomendado e estratégia comercial.",
    "tenant.proposal_options.view"
  ),
  tenantRoute(
    "tenant/operacional/pedidos-emissao",
    TenantPolicyRequestsPageComponent,
    "Pedidos de Emissão",
    "Handover de venda para emissão com vistoria e dados de cobrança.",
    "tenant.policy_requests.view"
  ),
  tenantRoute(
    "tenant/financeiro/visao-geral",
    TenantFinancePageComponent,
    "Financeiro",
    "Recebíveis, parcelas e inadimplência do tenant com integração ao operacional.",
    "tenant.finance.view"
  ),
  tenantPlaceholderRoute("tenant/financeiro/comissoes-fluxo", "Comissões/Fluxo"),
  tenantPlaceholderRoute("tenant/financeiro/parcelas-clientes", "Parcelas (Clientes)"),
  tenantPlaceholderRoute("tenant/financeiro/contas-pagar", "Contas a Pagar"),
  tenantPlaceholderRoute(
    "tenant/financeiro/conciliacao-bancos",
    "Conciliação Bancos (OFX)"
  ),
  tenantPlaceholderRoute("tenant/financeiro/fechamento-comissao", "Fechamento Comissão"),
  tenantRoute(
    "tenant/financeiro/notas-fiscais",
    TenantFiscalPageComponent,
    "Notas Fiscais",
    "Emissão, cancelamento e auditoria de documentos fiscais do tenant.",
    "tenant.fiscal.view"
  ),
  tenantPlaceholderRoute("tenant/financeiro/fiscal-config", "Fiscal"),
  tenantPlaceholderRoute("tenant/ferramentas/documentos", "Documentos"),
  tenantPlaceholderRoute("tenant/ferramentas/importar-clientes", "Importar Clientes"),
  tenantPlaceholderRoute("tenant/admin/sistema-monitor", "Sistema/Monitor"),
  tenantRoute(
    "tenant/admin/usuarios",
    TenantMembersPageComponent,
    "Usuários",
    "Gestão de usuários do tenant, papéis e contexto operacional.",
    "tenant.members.view"
  ),
  tenantRoute(
    "tenant/admin/auditoria",
    TenantLedgerPageComponent,
    "Auditoria",
    "Trilha de eventos e alterações do tenant para compliance e rastreabilidade.",
    "tenant.ledger.view"
  ),
  tenantRoute(
    "tenant/admin/rbac",
    TenantRbacPageComponent,
    "RBAC",
    "Matriz de permissões por papel, com validação de capacidades efetivas.",
    "tenant.rbac.manage"
  ),
];

const tenantLegacyAliasRoutes: Route[] = [
  aliasRoute("sales/flow", "tenant/comercial/fluxo"),
  aliasRoute("tenant/ai-assistant", "tenant/comercial/ai-assistente"),
  aliasRoute("tenant/customers", "tenant/comercial/clientes"),
  aliasRoute("tenant/leads", "tenant/comercial/leads"),
  aliasRoute("tenant/opportunities", "tenant/comercial/oportunidades"),
  aliasRoute("tenant/activities", "tenant/comercial/atividades"),
  aliasRoute("tenant/radar-leads", "tenant/comercial/radar-leads"),
  aliasRoute("tenant/special-projects", "tenant/comercial/projetos-especiais"),
  aliasRoute("tenant/goals", "tenant/comercial/metas"),
  aliasRoute("tenant/manager-view", "tenant/comercial/visao-gestor"),
  aliasRoute("tenant/messaging", "tenant/comercial/mensageria"),
  aliasRoute("tenant/insurers", "tenant/operacional/seguradoras"),
  aliasRoute("tenant/policies", "tenant/operacional/apolices"),
  aliasRoute("tenant/proposal-options", "tenant/operacional/propostas"),
  aliasRoute("tenant/policy-requests", "tenant/operacional/pedidos-emissao"),
  aliasRoute("tenant/finance", "tenant/financeiro/visao-geral"),
  aliasRoute("tenant/commissions-flow", "tenant/financeiro/comissoes-fluxo"),
  aliasRoute("tenant/installments-clients", "tenant/financeiro/parcelas-clientes"),
  aliasRoute("tenant/accounts-payable", "tenant/financeiro/contas-pagar"),
  aliasRoute("tenant/bank-reconciliation", "tenant/financeiro/conciliacao-bancos"),
  aliasRoute("tenant/commission-closing", "tenant/financeiro/fechamento-comissao"),
  aliasRoute("tenant/fiscal", "tenant/financeiro/notas-fiscais"),
  aliasRoute("tenant/fiscal-settings", "tenant/financeiro/fiscal-config"),
  aliasRoute("tenant/documents", "tenant/ferramentas/documentos"),
  aliasRoute("tenant/import-customers", "tenant/ferramentas/importar-clientes"),
  aliasRoute("tenant/system-monitor", "tenant/admin/sistema-monitor"),
  aliasRoute("tenant/ledger", "tenant/admin/auditoria"),
  aliasRoute("tenant/rbac", "tenant/admin/rbac"),
  aliasRoute("tenant/members", "tenant/admin/usuarios"),
  aliasRoute("tenant/comercial/equipe", "tenant/admin/usuarios"),
];

export const routes: Routes = [
  { path: "", pathMatch: "full", redirectTo: "login" },
  { path: "login", component: LoginPageComponent },
  { path: "forgot-password", component: ForgotPasswordPageComponent },
  { path: "reset-password", component: ResetPasswordPageComponent },
  ...tenantCanonicalRoutes,
  ...tenantLegacyAliasRoutes,
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
  { path: "**", redirectTo: "login" },
];
