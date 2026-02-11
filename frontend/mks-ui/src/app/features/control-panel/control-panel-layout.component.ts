import { CommonModule } from "@angular/common";
import { Component, OnDestroy, computed } from "@angular/core";
import { ScrollingModule } from "@angular/cdk/scrolling";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatListModule } from "@angular/material/list";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatToolbarModule } from "@angular/material/toolbar";
import {
  ActivatedRoute,
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from "@angular/router";
import { filter, Subscription } from "rxjs";

import { SessionService } from "../../core/auth/session.service";
import { BreadcrumbService } from "../../core/ui/breadcrumb.service";

interface ControlPanelNavItem {
  icon: string;
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
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
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
    { icon: "dashboard", label: "Dashboard", path: "/control-panel/dashboard", exact: true },
    { icon: "apartment", label: "Tenants", path: "/control-panel/tenants", exact: false },
    { icon: "workspace_premium", label: "Plans", path: "/control-panel/plans", exact: true },
    { icon: "description", label: "Contracts", path: "/control-panel/contracts", exact: true },
    { icon: "monitoring", label: "Monitoring", path: "/control-panel/monitoring", exact: true },
    { icon: "policy", label: "Audit", path: "/control-panel/audit", exact: true },
  ];

  constructor(
    private readonly router: Router,
    private readonly activatedRoute: ActivatedRoute,
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

  private updateBreadcrumbs(): void {
    this.breadcrumbService.buildFromRoute(this.activatedRoute, "Control Panel");
  }
}
