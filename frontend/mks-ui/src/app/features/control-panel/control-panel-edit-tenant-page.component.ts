import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

import { TenantDto } from "../../data-access/control-panel";
import { ControlPanelTenantFormComponent } from "./control-panel-tenant-form.component";

@Component({
  selector: "app-control-panel-edit-tenant-page",
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule, ControlPanelTenantFormComponent],
  templateUrl: "./control-panel-edit-tenant-page.component.html",
  styleUrl: "./control-panel-edit-tenant-page.component.scss",
})
export class ControlPanelEditTenantPageComponent implements OnInit {
  readonly tenantId = signal<number | null>(null);
  readonly error = signal("");

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    if (!Number.isFinite(id) || id <= 0) {
      this.error.set("ID de tenant inválido.");
      return;
    }
    this.tenantId.set(id);
  }

  onSaved(tenant: TenantDto): void {
    void this.router.navigate(["/control-panel/tenants", tenant.id]);
  }

  onCancelled(): void {
    const id = this.tenantId();
    if (id) {
      void this.router.navigate(["/control-panel/tenants", id]);
      return;
    }
    void this.router.navigate(["/control-panel/tenants"]);
  }
}
