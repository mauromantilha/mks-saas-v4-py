import { CommonModule } from "@angular/common";
import { Component, computed } from "@angular/core";
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";

import { AuthService } from "./core/api/auth.service";
import { PermissionService } from "./core/auth/permission.service";
import { SessionService } from "./core/auth/session.service";
import { PortalContextService } from "./core/portal/portal-context.service";
import { ThemeService } from "./core/theme/theme.service";

interface NavItem {
  label: string;
  path: string;
  exact?: boolean;
  accent?: string;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
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

  private readonly controlPlaneMenu: NavItem[] = [
    { label: "Dashboard", path: "/control-panel/dashboard", accent: "#f97316" },
    { label: "Tenants", path: "/control-panel/tenants", accent: "#fb7185" },
    { label: "Plans", path: "/control-panel/plans", accent: "#38bdf8" },
    { label: "Contracts", path: "/control-panel/contracts", accent: "#f59e0b" },
    { label: "Monitoring", path: "/control-panel/monitoring", accent: "#22c55e" },
    { label: "Audit", path: "/control-panel/audit", accent: "#64748b" },
  ];

  private readonly tenantMenuGroups: NavGroup[] = [
    {
      items: [{ label: "Dashboard", path: "/tenant/dashboard", exact: true, accent: "#0ea5e9" }],
    },
    {
      label: "Estratégia & Comercial",
      items: [
        { label: "IA Assistente", path: "/tenant/ai-assistant", accent: "#7c3aed" },
        { label: "Fluxo Comercial", path: "/sales/flow", accent: "#38bdf8" },
        { label: "Leads/Funil", path: "/tenant/leads", accent: "#f59e0b" },
        { label: "Radar de Leads", path: "/tenant/radar-leads", accent: "#f97316" },
        {
          label: "Projetos Especiais",
          path: "/tenant/special-projects",
          accent: "#8b5cf6",
        },
        { label: "Clientes", path: "/tenant/customers", accent: "#14b8a6" },
        { label: "Equipe/Produtores", path: "/tenant/members", accent: "#64748b" },
        { label: "Metas", path: "/tenant/goals", accent: "#0ea5e9" },
        { label: "Visão Gestor", path: "/tenant/manager-view", accent: "#0f766e" },
        { label: "Mensageria", path: "/tenant/messaging", accent: "#22c55e" },
        { label: "Atividade/Agenda", path: "/tenant/activities", accent: "#a855f7" },
      ],
    },
    {
      label: "Operacional",
      items: [
        { label: "Apólices", path: "/tenant/policies", accent: "#0f172a" },
        { label: "Seguradoras", path: "/tenant/insurers", accent: "#6366f1" },
        { label: "Propostas", path: "/tenant/proposal-options", accent: "#06b6d4" },
        { label: "Pedidos de Emissão", path: "/tenant/policy-requests", accent: "#22c55e" },
      ],
    },
    {
      label: "Financeiro",
      items: [
        { label: "Comissões/Fluxo", path: "/tenant/commissions-flow", accent: "#0284c7" },
        {
          label: "Parcelas (Clientes)",
          path: "/tenant/installments-clients",
          accent: "#14b8a6",
        },
        { label: "Contas a Pagar", path: "/tenant/accounts-payable", accent: "#b45309" },
        {
          label: "Conciliação Bancos (OFX)",
          path: "/tenant/bank-reconciliation",
          accent: "#475569",
        },
        {
          label: "Fechamento Comissão",
          path: "/tenant/commission-closing",
          accent: "#0369a1",
        },
        { label: "Notas Fiscais", path: "/tenant/fiscal", accent: "#16a34a" },
        { label: "Fiscal", path: "/tenant/fiscal-settings", accent: "#15803d" },
      ],
    },
    {
      label: "Ferramentas",
      items: [
        { label: "Documentos", path: "/tenant/documents", accent: "#2563eb" },
        { label: "Importar Clientes", path: "/tenant/import-customers", accent: "#0891b2" },
      ],
    },
    {
      label: "Admin",
      items: [
        { label: "Sistema/Monitor", path: "/tenant/system-monitor", accent: "#475569" },
        { label: "Usuários", path: "/tenant/members", accent: "#334155" },
        { label: "Auditoria", path: "/tenant/ledger", accent: "#94a3b8" },
        { label: "RBAC", path: "/tenant/rbac", accent: "#475569" },
      ],
    },
  ];

  readonly menuItems = computed<NavItem[]>(() => {
    const session = this.session();
    if (!session) {
      return [];
    }
    if (this.portalType() === "CONTROL_PLANE") {
      return session.platformAdmin ? this.controlPlaneMenu : [];
    }
    return this.tenantMenuGroups.flatMap((group) => group.items);
  });

  readonly tenantMenuGroupsView = computed<NavGroup[]>(() => {
    if (this.portalType() !== "TENANT") {
      return [];
    }
    return this.tenantMenuGroups;
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
    private readonly router: Router
  ) {
    // Keep theme service initialized at app bootstrap for auto system sync.
    void this.themeService.mode();
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
}
