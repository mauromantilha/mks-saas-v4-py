import { Routes } from "@angular/router";

import { authGuard } from "./core/auth/auth.guard";
import { LoginPageComponent } from "./features/auth/login-page.component";
import { PlatformTenantsPageComponent } from "./features/platform/platform-tenants-page.component";
import { SalesFlowPageComponent } from "./features/sales/sales-flow-page.component";
import { SectionPlaceholderPageComponent } from "./features/shared/section-placeholder-page.component";
import { TenantMembersPageComponent } from "./features/tenant-settings/tenant-members-page.component";
import { TenantRbacPageComponent } from "./features/tenant-settings/tenant-rbac-page.component";

export const routes: Routes = [
  { path: "", pathMatch: "full", redirectTo: "login" },
  { path: "login", component: LoginPageComponent },
  { path: "sales/flow", component: SalesFlowPageComponent, canActivate: [authGuard] },
  {
    path: "tenant/dashboard",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Painel do Tenant",
      description:
        "Resumo operacional do tenant: funil, emissão, renovação e alertas.",
    },
  },
  {
    path: "tenant/customers",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Clientes",
      description:
        "Cadastro completo de clientes e histórico comercial consolidado.",
    },
  },
  {
    path: "tenant/leads",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Leads",
      description:
        "Entrada de leads por webhook/API/importação, com enriquecimento por IA.",
    },
  },
  {
    path: "tenant/opportunities",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Oportunidades",
      description:
        "Gestão detalhada do pipeline comercial com etapas e KPIs de conversão.",
    },
  },
  {
    path: "tenant/activities",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Atividades e Follow-up",
      description:
        "Tarefas comerciais com SLA, lembretes e histórico por lead/oportunidade.",
    },
  },
  {
    path: "tenant/policy-requests",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Pedidos de Emissão",
      description:
        "Handover de venda para emissão com vistoria e dados de cobrança.",
    },
  },
  {
    path: "tenant/proposal-options",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Propostas Comparativas",
      description:
        "Comparativo de seguradoras, plano recomendado e estratégia comercial.",
    },
  },
  { path: "platform/tenants", component: PlatformTenantsPageComponent, canActivate: [authGuard] },
  {
    path: "platform/contracts",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Control Plane: Contratos",
      description:
        "Gestão de contrato, plano, assentos, vigência e cobrança de tenants.",
    },
  },
  {
    path: "platform/monitoring",
    component: SectionPlaceholderPageComponent,
    canActivate: [authGuard],
    data: {
      title: "Control Plane: Monitoramento",
      description:
        "Saúde de provisionamento, banco por tenant e telemetria operacional.",
    },
  },
  { path: "tenant/members", component: TenantMembersPageComponent, canActivate: [authGuard] },
  { path: "tenant/rbac", component: TenantRbacPageComponent, canActivate: [authGuard] },
  { path: "**", redirectTo: "login" },
];
