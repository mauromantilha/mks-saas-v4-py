import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

import { TenantDto } from "../../data-access/control-panel";
import { ControlPanelTenantFormComponent } from "./control-panel-tenant-form.component";

@Component({
  selector: "app-control-panel-create-tenant-page",
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule, ControlPanelTenantFormComponent],
  templateUrl: "./control-panel-create-tenant-page.component.html",
  styleUrl: "./control-panel-create-tenant-page.component.scss",
})
export class ControlPanelCreateTenantPageComponent {
  constructor(private readonly router: Router) {}

  onSaved(tenant: TenantDto): void {
    void this.router.navigate(["/control-panel/tenants", tenant.id]);
  }

  onCancelled(): void {
    void this.router.navigate(["/control-panel/tenants"]);
  }
}
