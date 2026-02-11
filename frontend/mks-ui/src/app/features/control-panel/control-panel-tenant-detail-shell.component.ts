import { CommonModule } from "@angular/common";
import { Component, OnInit, signal } from "@angular/core";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDialog } from "@angular/material/dialog";
import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { finalize } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import { PlanDto, TenantDto } from "../../data-access/control-panel";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { ConfirmDialogComponent, ConfirmDialogData } from "../../shared/ui/dialogs/confirm-dialog.component";
import { ControlPanelContractsTabComponent } from "./control-panel-contracts-tab.component";
import { ControlPanelFeaturesTabComponent } from "./control-panel-features-tab.component";
import { ControlPanelGovernanceTabComponent } from "./control-panel-governance-tab.component";
import { ControlPanelMonitoringTenantTabComponent } from "./control-panel-monitoring-tenant-tab.component";
import { ControlPanelNotesTabComponent } from "./control-panel-notes-tab.component";
import { ControlPanelSubscriptionTabComponent } from "./control-panel-subscription-tab.component";
import { ControlPanelTenantAuditTabComponent } from "./control-panel-tenant-audit-tab.component";

type DetailTab = "overview" | "subscription" | "contracts" | "monitoring" | "governance" | "features" | "notes" | "audit";

@Component({
  selector: "app-control-panel-tenant-detail-shell",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    PermissionDirective,
    MatTabsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    ControlPanelContractsTabComponent,
    ControlPanelFeaturesTabComponent,
    ControlPanelGovernanceTabComponent,
    ControlPanelMonitoringTenantTabComponent,
    ControlPanelNotesTabComponent,
    ControlPanelSubscriptionTabComponent,
    ControlPanelTenantAuditTabComponent,
  ],
  templateUrl: "./control-panel-tenant-detail-shell.component.html",
  styleUrl: "./control-panel-tenant-detail-shell.component.scss",
})
export class ControlPanelTenantDetailShellComponent implements OnInit {
  readonly tabs: DetailTab[] = [
    "overview",
    "subscription",
    "contracts",
    "monitoring",
    "governance",
    "features",
    "notes",
    "audit",
  ];

  readonly loading = signal(false);
  readonly actionLoading = signal(false);

  readonly tenant = signal<TenantDto | null>(null);
  readonly plans = signal<PlanDto[]>([]);
  readonly selectedTab = signal<DetailTab>("overview");

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly dialog: MatDialog,
    private readonly tenantApi: TenantApi,
    private readonly toast: ToastService
  ) {}

  ngOnInit(): void {
    const resolvedTenant = this.route.snapshot.data["tenant"] as TenantDto | undefined;
    const resolvedPlans = (this.route.snapshot.data["plans"] as PlanDto[] | undefined) ?? [];

    if (!resolvedTenant) {
      this.toast.error("Tenant não encontrado.");
      void this.router.navigate(["/control-panel/tenants"]);
      return;
    }

    this.tenant.set(resolvedTenant);
    this.plans.set(resolvedPlans);
  }

  onTabChange(index: number): void {
    const tab = this.tabs[index] ?? "overview";
    this.selectedTab.set(tab);
  }

  refreshTenant(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }
    this.loading.set(true);
    this.tenantApi
      .getTenant(tenant.id)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (updated) => {
          this.tenant.set(updated);
        },
        error: () => this.toast.error("Falha ao recarregar tenant."),
      });
  }

  suspendOrUnsuspend(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

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

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data,
      width: "560px",
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (!result?.confirmed) {
        return;
      }
      this.actionLoading.set(true);
      const request$ = isSuspended
        ? this.tenantApi.unsuspendTenant(tenant.id, { reason: result.reason || undefined })
        : this.tenantApi.suspendTenant(tenant.id, { reason: result.reason || undefined });

      request$.pipe(finalize(() => this.actionLoading.set(false))).subscribe({
        next: (updated) => {
          this.tenant.set(updated);
          this.toast.success(isSuspended ? "Tenant reativado." : "Tenant suspenso.");
        },
        error: () => this.toast.error("Não foi possível atualizar o status do tenant."),
      });
    });
  }

  softDelete(): void {
    const tenant = this.tenant();
    if (!tenant) {
      return;
    }

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

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data,
      width: "600px",
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (!result?.confirmed) {
        return;
      }
      this.actionLoading.set(true);
      this.tenantApi
        .deleteTenant(tenant.id, {
          confirm_text: result.confirmationText,
          reason: result.reason || undefined,
        })
        .pipe(finalize(() => this.actionLoading.set(false)))
        .subscribe({
          next: (updated) => {
            this.tenant.set(updated);
            this.toast.success("Tenant marcado como DELETED.");
          },
          error: () => this.toast.error("Não foi possível excluir o tenant."),
        });
    });
  }

  onSubscriptionUpdated(tenant: TenantDto): void {
    this.tenant.set(tenant);
  }
}
