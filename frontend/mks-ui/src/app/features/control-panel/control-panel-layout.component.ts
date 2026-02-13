import { CommonModule } from "@angular/common";
import { Component, OnDestroy, computed } from "@angular/core";
import { ScrollingModule } from "@angular/cdk/scrolling";
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from "@angular/router";
import { filter, Subscription } from "rxjs";
import { take } from "rxjs/operators";

import { AuthService } from "../../core/api/auth.service";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";
import { BreadcrumbService } from "../../core/ui/breadcrumb.service";

interface ControlPanelNavItem {
  label: string;
  path: string;
  exact?: boolean;
  permission?: string;
}

@Component({
  selector: "app-control-panel-layout",
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    ScrollingModule,
  ],
  templateUrl: "./control-panel-layout.component.html",
  styleUrl: "./control-panel-layout.component.scss",
})
export class ControlPanelLayoutComponent implements OnDestroy {
  private readonly subscriptions = new Subscription();

  readonly session = computed(() => this.sessionService.session());
  readonly breadcrumbs = computed(() => this.breadcrumbService.breadcrumbs());

  private readonly allMenuItems: ControlPanelNavItem[] = [
    {
      label: "Dashboard",
      path: "/control-panel/dashboard",
      exact: true,
      permission: "cp.dashboard.view",
    },
    {
      label: "Tenants",
      path: "/control-panel/tenants",
      exact: false,
      permission: "cp.tenants.view",
    },
    {
      label: "Plans",
      path: "/control-panel/plans",
      exact: true,
      permission: "cp.plans.view",
    },
    {
      label: "Contracts",
      path: "/control-panel/contracts",
      exact: true,
      permission: "cp.contracts.view",
    },
    {
      label: "Monitoring",
      path: "/control-panel/monitoring",
      exact: true,
      permission: "cp.monitoring.view",
    },
    {
      label: "Audit",
      path: "/control-panel/audit",
      exact: true,
      permission: "cp.audit.view",
    },
  ];
  readonly menuItems = computed(() =>
    this.allMenuItems.filter(
      (item) => !item.permission || this.permissionService.can(item.permission)
    )
  );

  constructor(
    private readonly router: Router,
    private readonly activatedRoute: ActivatedRoute,
    private readonly authService: AuthService,
    private readonly permissionService: PermissionService,
    private readonly sessionService: SessionService,
    private readonly breadcrumbService: BreadcrumbService
  ) {
    this.updateBreadcrumbs();
    this.permissionService.loadPermissions().pipe(take(1)).subscribe();
    this.subscriptions.add(
      this.router.events
        .pipe(filter((event) => event instanceof NavigationEnd))
        .subscribe(() => this.updateBreadcrumbs())
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  logout(): void {
    this.authService.clearAccessToken();
    this.permissionService.clearPermissions();
    this.sessionService.clearSession();
    void this.router.navigate(["/login"]);
  }

  private updateBreadcrumbs(): void {
    this.breadcrumbService.buildFromRoute(this.activatedRoute, "Control Panel");
  }
}
