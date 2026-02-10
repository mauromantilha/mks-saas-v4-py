import { CommonModule } from "@angular/common";
import { Component, computed } from "@angular/core";
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { MatSlideToggleChange, MatSlideToggleModule } from "@angular/material/slide-toggle";

import { SessionService } from "./core/auth/session.service";
import { PortalContextService } from "./core/portal/portal-context.service";
import { ThemeService } from "./core/theme/theme.service";

interface NavItem {
  label: string;
  path: string;
  exact?: boolean;
  accent?: string;
}

@Component({
  selector: "app-root",
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, MatSlideToggleModule],
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.scss",
})
export class AppComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly isAuthenticated = computed(() => this.sessionService.isAuthenticated());
  readonly isDarkMode = computed(() => this.themeService.isDarkMode());
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

  private readonly controlPlaneMenu: NavItem[] = [
    { label: "Tenants", path: "/platform/tenants", accent: "#f97316" },
    { label: "Contratos", path: "/platform/contracts", accent: "#fb7185" },
    { label: "Monitoramento", path: "/platform/monitoring", accent: "#f59e0b" },
  ];

  private readonly tenantMenu: NavItem[] = [
    { label: "Dashboard", path: "/tenant/dashboard", exact: true, accent: "#0ea5e9" },
    { label: "Fluxo Comercial", path: "/sales/flow", accent: "#38bdf8" },
    { label: "Clientes", path: "/tenant/customers", accent: "#14b8a6" },
    { label: "Leads", path: "/tenant/leads", accent: "#f59e0b" },
    { label: "Oportunidades", path: "/tenant/opportunities", accent: "#10b981" },
    { label: "Atividades", path: "/tenant/activities", accent: "#a855f7" },
    { label: "Seguradoras", path: "/tenant/insurers", accent: "#6366f1" },
    { label: "Financeiro", path: "/tenant/finance", accent: "#0f766e" },
    { label: "Apólices", path: "/tenant/policies", accent: "#0f172a" },
    { label: "Pedidos de Emissão", path: "/tenant/policy-requests", accent: "#22c55e" },
    { label: "Propostas", path: "/tenant/proposal-options", accent: "#06b6d4" },
    { label: "Membros", path: "/tenant/members", accent: "#64748b" },
    { label: "Fiscal (NF)", path: "/tenant/fiscal", accent: "#16a34a" },
    { label: "Auditoria", path: "/tenant/ledger", accent: "#94a3b8" },
    { label: "RBAC", path: "/tenant/rbac", accent: "#475569" },
  ];

  readonly menuItems = computed(() => {
    const session = this.session();
    if (!session) {
      return [];
    }
    if (this.portalType() === "CONTROL_PLANE") {
      return session.platformAdmin ? this.controlPlaneMenu : [];
    }
    return this.tenantMenu;
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
    private readonly portalContextService: PortalContextService,
    private readonly themeService: ThemeService,
    private readonly router: Router
  ) {}

  logout(): void {
    this.sessionService.clearSession();
    void this.router.navigate(["/login"]);
  }

  onThemeToggle(event: MatSlideToggleChange): void {
    this.themeService.setDarkMode(event.checked);
  }
}
