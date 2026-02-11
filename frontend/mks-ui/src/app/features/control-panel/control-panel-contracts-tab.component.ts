import { CommonModule } from "@angular/common";
import { Component, Input, OnChanges, SimpleChanges, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDialog } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { finalize } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { PermissionService } from "../../core/auth/permission.service";
import { ToastService } from "../../core/ui/toast.service";
import { ContractDto, PaginatedResponseDto } from "../../data-access/control-panel";
import { ContractsApi } from "../../data-access/control-panel/contracts-api.service";
import { ConfirmDialogComponent, ConfirmDialogData } from "../../shared/ui/dialogs/confirm-dialog.component";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";
import { ControlPanelContractDetailsDialogComponent } from "./control-panel-contract-details-dialog.component";

@Component({
  selector: "app-control-panel-contracts-tab",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PermissionDirective,
    MatCardModule,
    MatButtonModule,
    MatTableModule,
    MatSelectModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-contracts-tab.component.html",
  styleUrl: "./control-panel-contracts-tab.component.scss",
})
export class ControlPanelContractsTabComponent implements OnChanges {
  @Input({ required: true }) tenantId!: number;
  @Input() tenantEmail = "";

  readonly displayedColumns = ["id", "status", "created_at", "actions"];
  readonly statusOptions = [
    { value: "", label: "Todos os status" },
    { value: "DRAFT", label: "DRAFT" },
    { value: "SENT", label: "SENT" },
    { value: "SIGNED", label: "SIGNED" },
    { value: "CANCELLED", label: "CANCELLED" },
  ] as const;

  readonly loading = signal(false);
  readonly actionLoading = signal(false);
  readonly error = signal("");
  readonly contracts = signal<ContractDto[]>([]);
  readonly targetEmail = signal("");
  readonly statusFilter = signal<string>("");
  readonly searchFilter = signal<string>("");
  readonly pageIndex = signal(0);
  readonly pageSize = signal(10);

  readonly filteredContracts = computed(() => {
    const status = this.statusFilter();
    const search = this.searchFilter().trim().toLowerCase();

    return this.contracts().filter((contract) => {
      const statusMatch = !status || contract.status === status;
      const searchMatch =
        !search ||
        String(contract.id).includes(search) ||
        String(contract.contract_version ?? "").includes(search) ||
        String(contract.status || "").toLowerCase().includes(search);
      return statusMatch && searchMatch;
    });
  });

  readonly pagedContracts = computed(() => {
    const start = this.pageIndex() * this.pageSize();
    return this.filteredContracts().slice(start, start + this.pageSize());
  });

  constructor(
    private readonly contractsApi: ContractsApi,
    private readonly permissionService: PermissionService,
    private readonly dialog: MatDialog,
    private readonly toast: ToastService
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenantId"] && this.tenantId) {
      this.targetEmail.set(this.tenantEmail || "");
      this.loadContracts();
      return;
    }
    if (changes["tenantEmail"] && this.tenantEmail && !this.targetEmail()) {
      this.targetEmail.set(this.tenantEmail);
    }
  }

  reload(): void {
    this.pageIndex.set(0);
    this.loadContracts();
  }

  onStatusFilterChange(value: string): void {
    this.statusFilter.set(value || "");
    this.pageIndex.set(0);
  }

  onSearchChange(value: string): void {
    this.searchFilter.set(value || "");
    this.pageIndex.set(0);
  }

  onPageChanged(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  canManageContracts(): boolean {
    return this.permissionService.can("cp.tenants.manage");
  }

  createContractDraft(): void {
    if (!this.tenantId) {
      return;
    }
    this.actionLoading.set(true);
    this.contractsApi
      .createContract(this.tenantId)
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.toast.success("Draft de contrato criado.");
          this.loadContracts();
        },
        error: () => this.toast.error("Falha ao criar contrato."),
      });
  }

  sendContract(contract: ContractDto): void {
    const email = this.targetEmail().trim();
    if (!email || !this.isValidEmail(email)) {
      this.toast.warning("Informe um email válido para envio.");
      return;
    }

    const isResendBlockedStatus = contract.status === "SENT" || contract.status === "SIGNED";
    if (isResendBlockedStatus) {
      const data: ConfirmDialogData = {
        title: "Reenviar contrato",
        message:
          "Este contrato já está com status SENT/SIGNED. Deseja reenviar mesmo assim?",
        confirmLabel: "Reenviar",
        confirmColor: "warn",
      };
      const dialogRef = this.dialog.open(ConfirmDialogComponent, {
        data,
        width: "540px",
      });

      dialogRef.afterClosed().subscribe((result) => {
        if (!result?.confirmed) {
          return;
        }
        this.executeSend(contract.id, email, true);
      });
      return;
    }

    this.executeSend(contract.id, email, false);
  }

  openContractDetails(contractId: number): void {
    this.actionLoading.set(true);
    this.contractsApi
      .getContract(contractId)
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: (contract) => {
          this.dialog.open(ControlPanelContractDetailsDialogComponent, {
            data: contract,
            width: "840px",
          });
        },
        error: () => this.toast.error("Falha ao carregar detalhes do contrato."),
      });
  }

  private executeSend(contractId: number, toEmail: string, forceSend: boolean): void {
    this.actionLoading.set(true);
    this.contractsApi
      .sendContract(contractId, { to_email: toEmail, force_send: forceSend || undefined })
      .pipe(finalize(() => this.actionLoading.set(false)))
      .subscribe({
        next: () => {
          this.toast.success("Contrato enviado por email.");
          this.loadContracts();
        },
        error: () => this.toast.error("Falha ao enviar contrato."),
      });
  }

  private loadContracts(): void {
    if (!this.tenantId) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.contractsApi
      .listContracts(this.tenantId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.contracts.set(this.normalizeResponse(response));
          this.pageIndex.set(0);
        },
        error: () => {
          this.error.set("Falha ao carregar contratos.");
          this.contracts.set([]);
          this.toast.error("Falha ao carregar contratos.");
        },
      });
  }

  hasErrorState(): boolean {
    return !this.loading() && !!this.error();
  }

  hasEmptyState(): boolean {
    return !this.loading() && !this.error() && this.filteredContracts().length === 0;
  }

  private isValidEmail(email: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  private normalizeResponse(
    response: ContractDto[] | PaginatedResponseDto<ContractDto>
  ): ContractDto[] {
    if (Array.isArray(response)) {
      return response;
    }
    return response.results ?? [];
  }
}
