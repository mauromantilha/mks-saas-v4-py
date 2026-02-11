import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatSelectModule } from "@angular/material/select";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { finalize } from "rxjs";

import { TenantDto } from "../../data-access/control-panel";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";
import { ControlPanelContractsTabComponent } from "./control-panel-contracts-tab.component";

@Component({
  selector: "app-control-panel-contracts-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
    ControlPanelContractsTabComponent,
  ],
  templateUrl: "./control-panel-contracts-page.component.html",
  styleUrl: "./control-panel-contracts-page.component.scss",
})
export class ControlPanelContractsPageComponent implements OnInit {
  readonly loading = signal(false);
  readonly error = signal("");
  readonly tenants = signal<TenantDto[]>([]);
  readonly selectedTenantId = signal<number | null>(null);

  readonly selectedTenant = computed(() => {
    const tenantId = this.selectedTenantId();
    if (!tenantId) {
      return null;
    }
    return this.tenants().find((tenant) => tenant.id === tenantId) ?? null;
  });

  constructor(
    private readonly tenantApi: TenantApi,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.loadTenants();
  }

  onTenantChange(tenantId: number | null): void {
    this.selectedTenantId.set(tenantId);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tenant: tenantId || null },
      queryParamsHandling: "merge",
      replaceUrl: true,
    });
  }

  reload(): void {
    this.loadTenants();
  }

  private loadTenants(): void {
    this.loading.set(true);
    this.error.set("");
    this.tenantApi
      .listTenants({ page: 1, page_size: 500 })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          const items = response.items || [];
          this.tenants.set(items);

          const queryTenantId = Number(this.route.snapshot.queryParamMap.get("tenant"));
          if (Number.isFinite(queryTenantId) && items.some((tenant) => tenant.id === queryTenantId)) {
            this.selectedTenantId.set(queryTenantId);
            return;
          }

          const current = this.selectedTenantId();
          if (current && items.some((tenant) => tenant.id === current)) {
            return;
          }

          this.selectedTenantId.set(items.length > 0 ? items[0].id : null);
        },
        error: () => {
          this.error.set("Falha ao carregar tenants para gestão de contratos.");
          this.tenants.set([]);
          this.selectedTenantId.set(null);
        },
      });
  }
}
