import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";

interface ControlPanelNavItem {
  label: string;
  path: string;
  exact?: boolean;
}

@Component({
  selector: "app-control-panel-layout",
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: "./control-panel-layout.component.html",
  styleUrl: "./control-panel-layout.component.scss",
})
export class ControlPanelLayoutComponent {
  readonly menuItems: ControlPanelNavItem[] = [
    { label: "Dashboard", path: "/control-panel/dashboard", exact: true },
    { label: "Tenants", path: "/control-panel/tenants", exact: false },
    { label: "Plans", path: "/control-panel/plans", exact: true },
    { label: "Contracts", path: "/control-panel/contracts", exact: true },
    { label: "Monitoring", path: "/control-panel/monitoring", exact: true },
    { label: "Audit", path: "/control-panel/audit", exact: true },
  ];
}
