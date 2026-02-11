import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatTableModule } from "@angular/material/table";

import { PermissionService } from "../../core/auth/permission.service";
import { ToastService } from "../../core/ui/toast.service";
import { PlanDto } from "../../data-access/control-panel";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-plans-page",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatTableModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-plans-page.component.html",
  styleUrl: "./control-panel-plans-page.component.scss",
})
export class ControlPanelPlansPageComponent implements OnInit {
  readonly displayedColumns = ["name", "tier", "monthly_price", "setup_fee", "status"];

  readonly loading = signal(false);
  readonly error = signal("");
  readonly plans = signal<PlanDto[]>([]);

  constructor(
    private readonly plansApi: PlansApi,
    private readonly permissionService: PermissionService,
    private readonly toast: ToastService
  ) {}

  ngOnInit(): void {
    this.loadPlans();
  }

  reload(): void {
    this.loadPlans();
  }

  canManagePlans(): boolean {
    return this.permissionService.can("cp.plans.manage");
  }

  private loadPlans(): void {
    this.loading.set(true);
    this.error.set("");
    this.plansApi.listPlans().subscribe({
      next: (plans) => {
        this.plans.set(plans);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set("Falha ao carregar planos.");
        this.toast.error("Falha ao carregar planos.");
      },
    });
  }

  hasErrorState(): boolean {
    return !this.loading() && !!this.error();
  }

  hasEmptyState(): boolean {
    return !this.loading() && !this.error() && this.plans().length === 0;
  }
}
