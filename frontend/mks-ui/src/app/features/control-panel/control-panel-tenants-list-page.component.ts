import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";

import { PlatformTenantsService } from "../../core/api/platform-tenants.service";
import {
  PlanRecord,
  PlatformTenantRecord,
  TenantStatus,
  TenantListFilters,
} from "../../core/api/platform-tenants.types";

@Component({
  selector: "app-control-panel-tenants-list-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: "./control-panel-tenants-list-page.component.html",
  styleUrl: "./control-panel-tenants-list-page.component.scss",
})
export class ControlPanelTenantsListPageComponent implements OnInit {
  loading = signal(false);
  error = signal("");
  tenants = signal<PlatformTenantRecord[]>([]);
  plans = signal<PlanRecord[]>([]);

  readonly filtersForm = new FormGroup({
    status: new FormControl<string>(""),
    planId: new FormControl<number | null>(null),
    trial: new FormControl<"" | "true" | "false">(""),
    search: new FormControl<string>(""),
  });

  constructor(private readonly tenantsService: PlatformTenantsService) {}

  ngOnInit(): void {
    this.loadPlans();
    this.loadTenants();
  }

  loadPlans(): void {
    this.tenantsService.listPlans().subscribe({
      next: (plans) => this.plans.set(plans),
      error: () => {
        this.error.set("Falha ao carregar planos para filtros.");
      },
    });
  }

  loadTenants(): void {
    this.loading.set(true);
    this.error.set("");
    const raw = this.filtersForm.getRawValue();
    const filters: TenantListFilters = {
      status: (raw.status || "") as TenantStatus | "",
      planId: raw.planId,
      trial: raw.trial || "",
      search: raw.search || "",
    };
    this.tenantsService.listTenants(filters).subscribe({
      next: (tenants) => {
        this.tenants.set(tenants);
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Falha ao carregar tenants.");
        this.loading.set(false);
      },
    });
  }

  clearFilters(): void {
    this.filtersForm.reset({
      status: "",
      planId: null,
      trial: "",
      search: "",
    });
    this.loadTenants();
  }
}
