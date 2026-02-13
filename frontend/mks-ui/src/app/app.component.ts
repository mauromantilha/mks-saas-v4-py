import { CommonModule } from "@angular/common";
import { Component, computed, effect, untracked } from "@angular/core";
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { take } from "rxjs/operators";

import { AuthService } from "./core/api/auth.service";
import { PermissionService } from "./core/auth/permission.service";
import { SessionService } from "./core/auth/session.service";
import { PortalContextService } from "./core/portal/portal-context.service";
import { ThemeService } from "./core/theme/theme.service";
import { MenuVersionService } from "./core/ui/menu-version.service";

interface NavItem {
  label: string;
  path: string;
  exact?: boolean;
  accent?: string;
  permission?: string;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

interface TenantNavItem extends Omit<NavItem, "path"> {
  pathLegacy: string;
  pathV2: string;
}

interface TenantNavGroup {
  label?: string;
  items: TenantNavItem[];
}

@Component({
  selector: "app-root",
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.scss",
})
export class AppComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly isAuthenticated = computed(() => this.sessionService.isAuthenticated());
  readonly hostname = this.portalContextService.hostname();
  readonly portalType = computed(() => {
    const hostPortal = this.portalContextService.portalType();
    // On real domains we must trust the host to avoid mixing Control Plane vs Tenant UI.
    // On plain localhost the host is ambiguous, so we allow the session choice.
    if (this.hostname === "localhost" || this.hostname === "127.0.0.1") {
      return this.session()?.portalType ?? hostPortal;
    }
    return hostPortal;
  });
  readonly isControlPlanePortal = computed(() => this.portalType() === "CONTROL_PLANE");
  readonly isControlPanelRoute = computed(() => this.router.url.startsWith("/control-panel"));
  readonly isMenuV2Enabled = computed(() => this.menuVersionService.isMenuV2Enabled());

  private readonly controlPlaneMenu: NavItem[] = [
    {
      label: "Dashboard",
      path: "/control-panel/dashboard",
      accent: "#f97316",
      permission: "cp.dashboard.view",
    },
    {
      label: "Tenants",
      path: "/control-panel/tenants",
      accent: "#fb7185",
      permission: "cp.tenants.view",
    },
    {
      label: "Plans",
      path: "/control-panel/plans",
      accent: "#38bdf8",
      permission: "cp.plans.view",
    },
    {
      label: "Contracts",
      path: "/control-panel/contracts",
      accent: "#f59e0b",
      permission: "cp.contracts.view",
    },
    {
      label: "Monitoring",
      path: "/control-panel/monitoring",
      accent: "#22c55e",
      permission: "cp.monitoring.view",
    },
    {
      label: "Audit",
      path: "/control-panel/audit",
      accent: "#64748b",
      permission: "cp.audit.view",
    },
  ];

  private readonly tenantMenuGroups: TenantNavGroup[] = [
    {
      items: [
        {
          label: "Dashboard",
          pathLegacy: "/tenant/dashboard",
          pathV2: "/tenant/dashboard",
          exact: true,
          accent: "#0ea5e9",
          permission: "tenant.dashboard.view",
        },
      ],
    },
    {
      label: "Estratégia & Comercial",
      items: [
        {
          label: "MKS Advisor",
          pathLegacy: "/tenant/ai-assistant",
          pathV2: "/tenant/comercial/ai-assistente",
          accent: "#7c3aed",
          permission: "tenant.ai_assistant.view",
        },
        {
          label: "Fluxo Comercial",
          pathLegacy: "/sales/flow",
          pathV2: "/tenant/comercial/fluxo",
          accent: "#38bdf8",
        },
        {
          label: "Leads/Funil",
          pathLegacy: "/tenant/leads",
          pathV2: "/tenant/comercial/leads",
          accent: "#f59e0b",
          permission: "tenant.leads.view",
        },
        {
          label: "Radar de Leads",
          pathLegacy: "/tenant/radar-leads",
          pathV2: "/tenant/comercial/radar-leads",
          accent: "#f97316",
        },
        {
          label: "Projetos Especiais",
          pathLegacy: "/tenant/special-projects",
          pathV2: "/tenant/comercial/projetos-especiais",
          accent: "#8b5cf6",
        },
        {
          label: "Clientes",
          pathLegacy: "/tenant/customers",
          pathV2: "/tenant/comercial/clientes",
          accent: "#14b8a6",
          permission: "tenant.customers.view",
        },
        {
          label: "Equipe/Produtores",
          pathLegacy: "/tenant/members",
          pathV2: "/tenant/comercial/equipe",
          accent: "#64748b",
        },
        {
          label: "Metas",
          pathLegacy: "/tenant/goals",
          pathV2: "/tenant/comercial/metas",
          accent: "#0ea5e9",
        },
        {
          label: "Visão Gestor",
          pathLegacy: "/tenant/manager-view",
          pathV2: "/tenant/comercial/visao-gestor",
          accent: "#0f766e",
        },
        {
          label: "Mensageria",
          pathLegacy: "/tenant/messaging",
          pathV2: "/tenant/comercial/mensageria",
          accent: "#22c55e",
        },
        {
          label: "Atividade/Agenda",
          pathLegacy: "/tenant/activities",
          pathV2: "/tenant/comercial/atividades",
          accent: "#a855f7",
          permission: "tenant.activities.view",
        },
      ],
    },
    {
      label: "Operacional",
      items: [
        {
          label: "Apólices",
          pathLegacy: "/tenant/policies",
          pathV2: "/tenant/operacional/apolices",
          accent: "#0f172a",
          permission: "tenant.apolices.view",
        },
        {
          label: "Seguradoras",
          pathLegacy: "/tenant/insurers",
          pathV2: "/tenant/operacional/seguradoras",
          accent: "#6366f1",
          permission: "tenant.insurers.view",
        },
        {
          label: "Propostas",
          pathLegacy: "/tenant/proposal-options",
          pathV2: "/tenant/operacional/propostas",
          accent: "#06b6d4",
          permission: "tenant.proposal_options.view",
        },
        {
          label: "Pedidos de Emissão",
          pathLegacy: "/tenant/policy-requests",
          pathV2: "/tenant/operacional/pedidos-emissao",
          accent: "#22c55e",
          permission: "tenant.policy_requests.view",
        },
      ],
    },
    {
      label: "Financeiro",
      items: [
        {
          label: "Comissões/Fluxo",
          pathLegacy: "/tenant/commissions-flow",
          pathV2: "/tenant/financeiro/comissoes-fluxo",
          accent: "#0284c7",
          permission: "tenant.commissions.view",
        },
        {
          label: "Parcelas (Clientes)",
          pathLegacy: "/tenant/installments-clients",
          pathV2: "/tenant/financeiro/parcelas-clientes",
          accent: "#14b8a6",
          permission: "tenant.installments.view",
        },
        {
          label: "Contas a Pagar",
          pathLegacy: "/tenant/accounts-payable",
          pathV2: "/tenant/financeiro/contas-pagar",
          accent: "#b45309",
          permission: "tenant.payables.view",
        },
        {
          label: "Conciliação Bancos (OFX)",
          pathLegacy: "/tenant/bank-reconciliation",
          pathV2: "/tenant/financeiro/conciliacao-bancos",
          accent: "#475569",
        },
        {
          label: "Fechamento Comissão",
          pathLegacy: "/tenant/commission-closing",
          pathV2: "/tenant/financeiro/fechamento-comissao",
          accent: "#0369a1",
        },
        {
          label: "Notas Fiscais",
          pathLegacy: "/tenant/fiscal",
          pathV2: "/tenant/financeiro/notas-fiscais",
          accent: "#16a34a",
          permission: "tenant.fiscal.view",
        },
        {
          label: "Fiscal",
          pathLegacy: "/tenant/fiscal-settings",
          pathV2: "/tenant/financeiro/fiscal-config",
          accent: "#15803d",
          permission: "tenant.fiscal.view",
        },
      ],
    },
    {
      label: "Ferramentas",
      items: [
        {
          label: "Documentos",
          pathLegacy: "/tenant/documents",
          pathV2: "/tenant/ferramentas/documentos",
          accent: "#2563eb",
        },
        {
          label: "Importar Clientes",
          pathLegacy: "/tenant/import-customers",
          pathV2: "/tenant/ferramentas/importar-clientes",
          accent: "#0891b2",
        },
      ],
    },
    {
      label: "Admin",
      items: [
        {
          label: "Sistema/Monitor",
          pathLegacy: "/tenant/system-monitor",
          pathV2: "/tenant/admin/sistema-monitor",
          accent: "#475569",
        },
        {
          label: "Usuários",
          pathLegacy: "/tenant/members",
          pathV2: "/tenant/admin/usuarios",
          accent: "#334155",
          permission: "tenant.members.view",
        },
        {
          label: "Auditoria",
          pathLegacy: "/tenant/ledger",
          pathV2: "/tenant/admin/auditoria",
          accent: "#94a3b8",
          permission: "tenant.ledger.view",
        },
        {
          label: "RBAC",
          pathLegacy: "/tenant/rbac",
          pathV2: "/tenant/admin/rbac",
          accent: "#475569",
          permission: "tenant.rbac.manage",
        },
      ],
    },
  ];

  readonly menuItems = computed<NavItem[]>(() => {
    const session = this.session();
    if (!session) {
      return [];
    }
    if (this.portalType() === "CONTROL_PLANE") {
      return session.platformAdmin
        ? this.controlPlaneMenu.filter((item) => this.canRenderMenuItem(item))
        : [];
    }
    return this.tenantMenuGroupsView().flatMap((group) => group.items);
  });

  readonly tenantMenuGroupsView = computed<NavGroup[]>(() => {
    if (this.portalType() !== "TENANT") {
      return [];
    }
    const useMenuV2 = this.isMenuV2Enabled();
    return this.tenantMenuGroups
      .map((group) => ({
        label: group.label,
        items: group.items
          .filter((item) => this.canRenderMenuItem(item))
          .map((item) => ({
            label: item.label,
            path: this.resolveTenantPath(item, useMenuV2),
            exact: item.exact,
            accent: item.accent,
          })),
      }))
      .filter((group) => group.items.length > 0);
  });

  readonly portalTitle = computed(() => {
    if (this.portalType() === "CONTROL_PLANE") {
      return "Portal Sistema";
    }
    return "Portal Tenant";
  });

  readonly brandTitle = computed(() => {
    if (this.portalType() === "CONTROL_PLANE") {
      return "MKS Sistema";
    }
    return "MKS CRM";
  });

  constructor(
    public readonly sessionService: SessionService,
    private readonly authService: AuthService,
    private readonly permissionService: PermissionService,
    private readonly portalContextService: PortalContextService,
    private readonly themeService: ThemeService,
    private readonly menuVersionService: MenuVersionService,
    private readonly router: Router
  ) {
    // Keep theme service initialized at app bootstrap for auto system sync.
    void this.themeService.mode();
    effect(() => {
      const currentSession = this.session();
      const currentPortal = this.portalType();
      untracked(() => {
        this.menuVersionService.resolveForTenant(currentSession, currentPortal);
      });
    });
    effect(() => {
      const session = this.session();
      if (!session?.token) {
        return;
      }
      untracked(() => {
        this.permissionService.loadPermissions().pipe(take(1)).subscribe();
      });
    });
  }

  shouldShowLegacySidebar(): boolean {
    return this.isAuthenticated() && !this.isControlPlanePortal() && !this.isControlPanelRoute();
  }

  logout(): void {
    this.authService.clearAccessToken();
    this.permissionService.clearPermissions();
    this.sessionService.clearSession();
    void this.router.navigate(["/login"]);
  }

  private resolveTenantPath(item: TenantNavItem, useMenuV2: boolean): string {
    return useMenuV2 ? item.pathV2 : item.pathLegacy;
  }

  private canRenderMenuItem(item: { permission?: string }): boolean {
    if (!item.permission) {
      return true;
    }
    return this.permissionService.can(item.permission);
  }
}
