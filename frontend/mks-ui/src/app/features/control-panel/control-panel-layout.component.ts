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

import { AuthService } from "../../core/api/auth.service";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";
import { BreadcrumbService } from "../../core/ui/breadcrumb.service";

interface ControlPanelNavItem {
  label: string;
  path: string;
  exact?: boolean;
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

  readonly menuItems: ControlPanelNavItem[] = [
    { label: "Dashboard", path: "/control-panel/dashboard", exact: true },
    { label: "Tenants", path: "/control-panel/tenants", exact: false },
    { label: "Plans", path: "/control-panel/plans", exact: true },
    { label: "Contracts", path: "/control-panel/contracts", exact: true },
    { label: "Monitoring", path: "/control-panel/monitoring", exact: true },
    { label: "Audit", path: "/control-panel/audit", exact: true },
  ];

  constructor(
    private readonly router: Router,
    private readonly activatedRoute: ActivatedRoute,
    private readonly authService: AuthService,
    private readonly permissionService: PermissionService,
    private readonly sessionService: SessionService,
    private readonly breadcrumbService: BreadcrumbService
  ) {
    this.updateBreadcrumbs();
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
