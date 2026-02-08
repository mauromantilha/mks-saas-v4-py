import { CommonModule } from "@angular/common";
import { Component, computed } from "@angular/core";
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";

import { SessionService } from "./core/auth/session.service";
import { PortalContextService } from "./core/portal/portal-context.service";

interface NavItem {
  label: string;
  path: string;
  exact?: boolean;
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
  readonly portalType = computed(() => {
    const session = this.session();
    // Prefer the portal type chosen during login; fall back to hostname detection.
    return session?.portalType ?? this.portalContextService.portalType();
  });
  readonly hostname = this.portalContextService.hostname();

  private readonly controlPlaneMenu: NavItem[] = [
    { label: "Tenants", path: "/platform/tenants" },
    { label: "Contratos", path: "/platform/contracts" },
    { label: "Monitoramento", path: "/platform/monitoring" },
  ];

  private readonly tenantMenu: NavItem[] = [
    { label: "Fluxo Comercial", path: "/sales/flow" },
    { label: "Painel Tenant", path: "/tenant/dashboard" },
    { label: "Clientes", path: "/tenant/customers" },
    { label: "Leads", path: "/tenant/leads" },
    { label: "Oportunidades", path: "/tenant/opportunities" },
    { label: "Atividades", path: "/tenant/activities" },
    { label: "Pedidos de Emissão", path: "/tenant/policy-requests" },
    { label: "Propostas", path: "/tenant/proposal-options" },
    { label: "Membros", path: "/tenant/members" },
    { label: "RBAC", path: "/tenant/rbac" },
  ];

  readonly menuItems = computed(() => {
    const session = this.session();
    if (!session) {
      return [];
    }
    if (this.portalType() === "CONTROL_PLANE" && session.platformAdmin) {
      return this.controlPlaneMenu;
    }
    return this.tenantMenu;
  });

  readonly portalTitle = computed(() => {
    if (this.portalType() === "CONTROL_PLANE") {
      return "Control Plane";
    }
    return "Portal Tenant";
  });

  constructor(
    public readonly sessionService: SessionService,
    private readonly portalContextService: PortalContextService,
    private readonly router: Router
  ) {}

  logout(): void {
    this.sessionService.clearSession();
    void this.router.navigate(["/login"]);
  }
}
