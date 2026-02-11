import { CommonModule } from "@angular/common";
import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatDialog } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { PageEvent, MatPaginatorModule } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { Router, RouterLink } from "@angular/router";
import { debounceTime, distinctUntilChanged, finalize, map } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import {
  PlanDto,
  TenantDto,
  TenantListParams,
  TenantStatus,
} from "../../data-access/control-panel";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { ConfirmDialogComponent, ConfirmDialogData } from "../../shared/ui/dialogs/confirm-dialog.component";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-tenants-list-page",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    PermissionDirective,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCardModule,
    MatChipsModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-tenants-list-page.component.html",
  styleUrl: "./control-panel-tenants-list-page.component.scss",
})
export class ControlPanelTenantsListPageComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  readonly displayedColumns = [
    "legal_name",
    "slug",
    "status",
    "plan",
    "trial_ends_at",
    "created_at",
    "actions",
  ];

  readonly loading = signal(false);
  readonly error = signal("");
  readonly tenants = signal<TenantDto[]>([]);
  readonly plans = signal<PlanDto[]>([]);
  readonly totalRows = signal(0);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(10);

  readonly filtersForm = new FormGroup({
    status: new FormControl<TenantStatus | "">("", { nonNullable: true }),
    planId: new FormControl<string>("", { nonNullable: true }),
    trial: new FormControl<"" | "true" | "false">("", { nonNullable: true }),
    search: new FormControl<string>("", { nonNullable: true }),
  });

  constructor(
    private readonly router: Router,
    private readonly dialog: MatDialog,
    private readonly tenantApi: TenantApi,
    private readonly plansApi: PlansApi,
    private readonly toast: ToastService
  ) {}

  ngOnInit(): void {
    this.loadPlans();
    this.filtersForm.valueChanges
      .pipe(
        debounceTime(300),
        map((value) => JSON.stringify(value)),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => this.loadTenants(true));
    this.loadTenants(true);
  }

  loadPlans(): void {
    this.plansApi.listPlans().subscribe({
      next: (plans) => this.plans.set(plans),
      error: () => {
        this.toast.error("Falha ao carregar planos para filtros.");
      },
    });
  }

  loadTenants(resetPage = false): void {
    if (resetPage) {
      this.pageIndex.set(0);
    }

    this.loading.set(true);
    this.error.set("");

    const raw = this.filtersForm.getRawValue();
    const filters: TenantListParams = {
      status: raw.status || "",
      plan: this.parsePlanFilter(raw.planId),
      trial: this.parseTrialFilter(raw.trial || ""),
      search: raw.search || "",
      page: this.pageIndex() + 1,
      page_size: this.pageSize(),
    };

    this.tenantApi
      .listTenants(filters)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.tenants.set(response.items);
          this.totalRows.set(response.total);
        },
        error: () => {
          this.error.set("Falha ao carregar tenants.");
        },
      });
  }

  clearFilters(): void {
    this.filtersForm.reset(
      {
        status: "",
        planId: "",
        trial: "",
        search: "",
      },
      { emitEvent: false }
    );
    this.loadTenants(true);
  }

  reload(): void {
    this.loadTenants();
  }

  onPageChanged(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.loadTenants();
  }

  openDetails(tenant: TenantDto): void {
    void this.router.navigate(["/control-panel/tenants", tenant.id]);
  }

  toggleSuspension(tenant: TenantDto): void {
    const isSuspended = tenant.status === "SUSPENDED";
    const data: ConfirmDialogData = {
      title: isSuspended ? "Reativar tenant" : "Suspender tenant",
      message: isSuspended
        ? `Confirma reativar o tenant ${tenant.legal_name}?`
        : `Confirma suspender o tenant ${tenant.legal_name}?`,
      confirmLabel: isSuspended ? "Reativar" : "Suspender",
      confirmColor: isSuspended ? "primary" : "warn",
      reasonLabel: "Motivo (opcional)",
    };

    const dialogRef = this.dialog.open(ConfirmDialogComponent, { data, width: "560px" });
    dialogRef.afterClosed().subscribe((result) => {
      if (!result?.confirmed) {
        return;
      }

      this.loading.set(true);
      const request$ = isSuspended
        ? this.tenantApi.unsuspendTenant(tenant.id, { reason: result.reason || undefined })
        : this.tenantApi.suspendTenant(tenant.id, { reason: result.reason || undefined });

      request$.pipe(finalize(() => this.loading.set(false))).subscribe({
        next: () => {
          this.toast.success(
            isSuspended ? "Tenant reativado com sucesso." : "Tenant suspenso com sucesso."
          );
          this.loadTenants();
        },
        error: () => {
          this.toast.error(
            isSuspended
              ? "Não foi possível reativar o tenant."
              : "Não foi possível suspender o tenant."
          );
        },
      });
    });
  }

  deleteTenant(tenant: TenantDto): void {
    const data: ConfirmDialogData = {
      title: "Excluir tenant (soft delete)",
      message:
        "Esta ação marcará o tenant como DELETED e bloqueará acesso. Digite o slug para confirmar.",
      confirmLabel: "Excluir",
      confirmColor: "warn",
      requireText: tenant.slug,
      requireTextLabel: "Confirme o slug",
      reasonLabel: "Motivo (obrigatório)",
      reasonRequired: true,
    };

    const dialogRef = this.dialog.open(ConfirmDialogComponent, { data, width: "580px" });
    dialogRef.afterClosed().subscribe((result) => {
      if (!result?.confirmed) {
        return;
      }

      this.loading.set(true);
      this.tenantApi
        .deleteTenant(tenant.id, {
          confirm_text: result.confirmationText,
          reason: result.reason || undefined,
        })
        .pipe(finalize(() => this.loading.set(false)))
        .subscribe({
          next: () => {
            this.toast.success("Tenant marcado como DELETED.");
            this.loadTenants();
          },
          error: () => {
            this.toast.error("Não foi possível excluir o tenant.");
          },
        });
    });
  }

  tenantPlan(tenant: TenantDto): string {
    return tenant.subscription?.plan?.name ?? tenant.plan_name ?? "-";
  }

  tenantTrialEndsAt(tenant: TenantDto): string | null {
    return tenant.subscription?.trial_ends_at ?? tenant.trial_ends_at ?? null;
  }

  isTrial(tenant: TenantDto): boolean {
    return tenant.subscription?.is_trial ?? tenant.is_trial ?? false;
  }

  hasLoading(): boolean {
    return this.loading();
  }

  hasErrorState(): boolean {
    return !this.loading() && !!this.error();
  }

  hasEmptyState(): boolean {
    return !this.loading() && !this.error() && this.tenants().length === 0;
  }

  hasDataState(): boolean {
    return !this.loading() && !this.error() && this.tenants().length > 0;
  }

  errorMessage(): string {
    return this.error() || "Falha ao carregar tenants.";
  }

  private parseTrialFilter(value: "" | "true" | "false"): boolean | "" {
    if (value === "") {
      return "";
    }
    return value === "true";
  }

  private parsePlanFilter(value: string): number | null {
    if (!value) {
      return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
}
