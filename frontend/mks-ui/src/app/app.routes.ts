import { Routes } from "@angular/router";

import { authGuard } from "./core/auth/auth.guard";
import { portalGuard } from "./core/portal/portal.guard";
import { ForgotPasswordPageComponent } from "./features/auth/forgot-password-page.component";
import { LoginPageComponent } from "./features/auth/login-page.component";
import { ResetPasswordPageComponent } from "./features/auth/reset-password-page.component";
import { PlatformTenantsPageComponent } from "./features/platform/platform-tenants-page.component";
import { SalesFlowPageComponent } from "./features/sales/sales-flow-page.component";
import { SectionPlaceholderPageComponent } from "./features/shared/section-placeholder-page.component";
import { TenantActivitiesPageComponent } from "./features/tenant/tenant-activities-page.component";
import { TenantCustomersPageComponent } from "./features/tenant/tenant-customers-page.component";
import { TenantDashboardPageComponent } from "./features/tenant/tenant-dashboard-page.component";
import { TenantInsurersPageComponent } from "./features/tenant/tenant-insurers-page.component";
import { TenantLeadsPageComponent } from "./features/tenant/tenant-leads-page.component";
import { TenantOpportunitiesPageComponent } from "./features/tenant/tenant-opportunities-page.component";
import { TenantFinancePageComponent } from "./features/tenant/tenant-finance-page.component";
import { TenantPoliciesPageComponent } from "./features/tenant/tenant-policies-page.component";
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
    component: SectionPlaceholderPageComponent,
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
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "TENANT",
      title: "Propostas Comparativas",
      description:
        "Comparativo de seguradoras, plano recomendado e estratégia comercial.",
    },
  },
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
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard, portalGuard],
    data: {
      portal: "CONTROL_PLANE",
      title: "Control Plane: Monitoramento",
      description:
        "Saúde de provisionamento, banco por tenant e telemetria operacional.",
    },
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
    path: "tenant/rbac",
    component: TenantRbacPageComponent,
    canActivate: [authGuard, portalGuard],
    data: { portal: "TENANT" },
  },
  { path: "**", redirectTo: "login" },
];
