import { CommonModule } from "@angular/common";
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from "@angular/core";
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatDialog } from "@angular/material/dialog";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { finalize } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { PermissionService } from "../../core/auth/permission.service";
import { ToastService } from "../../core/ui/toast.service";
import { PlanDto, TenantDto } from "../../data-access/control-panel";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { ConfirmDialogComponent, ConfirmDialogData } from "../../shared/ui/dialogs/confirm-dialog.component";
import { normalizeAndApplyApiFormError } from "../../shared/forms/api-form-errors.util";

@Component({
  selector: "app-control-panel-subscription-tab",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    PermissionDirective,
  ],
  templateUrl: "./control-panel-subscription-tab.component.html",
  styleUrl: "./control-panel-subscription-tab.component.scss",
})
export class ControlPanelSubscriptionTabComponent implements OnChanges {
  @Input({ required: true }) tenant!: TenantDto;
  @Input({ required: true }) plans: PlanDto[] = [];
  @Output() updated = new EventEmitter<TenantDto>();

  readonly saving = new FormControl(false, { nonNullable: true });

  readonly form = new FormGroup({
    plan_id: new FormControl<number | null>(null, [Validators.required]),
    is_trial: new FormControl<boolean>(false, { nonNullable: true }),
    trial_days: new FormControl<number | null>(null, [Validators.min(1), Validators.max(90)]),
    is_courtesy: new FormControl<boolean>(false, { nonNullable: true }),
    setup_fee_override: new FormControl<string>("", { nonNullable: true }),
  });

  private currentPlanId: number | null = null;

  constructor(
    private readonly plansApi: PlansApi,
    private readonly permissionService: PermissionService,
    private readonly dialog: MatDialog,
    private readonly toast: ToastService
  ) {
    this.form.controls.is_trial.valueChanges.subscribe((isTrial) => {
      if (isTrial) {
        this.form.controls.trial_days.addValidators([Validators.required]);
        if (!this.form.controls.trial_days.value) {
          this.form.controls.trial_days.setValue(7);
        }
      } else {
        this.form.controls.trial_days.removeValidators([Validators.required]);
        this.form.controls.trial_days.setValue(null);
      }
      this.form.controls.trial_days.updateValueAndValidity({ emitEvent: false });
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenant"] && this.tenant) {
      this.currentPlanId = this.tenant.subscription?.plan?.id ?? null;
      const defaultSetupFee = this.resolvePlanSetupFee(this.currentPlanId);

      this.form.patchValue(
        {
          plan_id: this.currentPlanId,
          is_trial: this.tenant.subscription?.is_trial ?? false,
          trial_days: this.tenant.subscription?.is_trial ? 7 : null,
          is_courtesy: this.tenant.subscription?.is_courtesy ?? false,
          setup_fee_override: this.normalizeSetupFee(
            this.tenant.subscription?.setup_fee_override ??
              (defaultSetupFee ? String(defaultSetupFee) : "")
          ),
        },
        { emitEvent: false }
      );
      this.applyPermissionState();
    }
  }

  canManagePlans(): boolean {
    return this.permissionService.can("cp.plans.manage");
  }

  effectiveFrom(): string | null {
    return this.tenant.subscription?.start_date ?? null;
  }

  save(): void {
    if (!this.canManagePlans()) {
      return;
    }

    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.toast.warning("Revise os campos da assinatura.");
      return;
    }

    const raw = this.form.getRawValue();
    if (!raw.plan_id) {
      this.toast.warning("Selecione um plano.");
      return;
    }

    const saveAction = () => {
      this.saving.setValue(true, { emitEvent: false });
      this.plansApi
        .updateTenantSubscription(this.tenant.id, {
          plan_id: raw.plan_id!,
          is_trial: raw.is_trial ?? false,
          trial_days: raw.is_trial ? Number(raw.trial_days || 7) : undefined,
          is_courtesy: raw.is_courtesy ?? false,
          setup_fee_override: raw.setup_fee_override ? raw.setup_fee_override : null,
        })
        .pipe(finalize(() => this.saving.setValue(false, { emitEvent: false })))
        .subscribe({
          next: (tenant) => {
            this.toast.success("Assinatura atualizada com sucesso.");
            this.updated.emit(tenant);
          },
          error: (error) => {
            const message = normalizeAndApplyApiFormError(
              this.form,
              error,
              "Falha ao atualizar assinatura."
            );
            this.toast.error(message);
          },
        });
    };

    if (raw.plan_id !== this.currentPlanId) {
      const oldPlanLabel = this.resolvePlanName(this.currentPlanId);
      const newPlanLabel = this.resolvePlanName(raw.plan_id);

      const data: ConfirmDialogData = {
        title: "Confirmar troca de plano",
        message: `Você está alterando o plano de "${oldPlanLabel}" para "${newPlanLabel}". Deseja continuar?`,
        confirmLabel: "Confirmar troca",
        confirmColor: "warn",
      };

      const dialogRef = this.dialog.open(ConfirmDialogComponent, {
        data,
        width: "560px",
      });
      dialogRef.afterClosed().subscribe((result) => {
        if (!result?.confirmed) {
          return;
        }
        saveAction();
      });
      return;
    }

    saveAction();
  }

  private applyPermissionState(): void {
    if (this.canManagePlans()) {
      this.form.enable({ emitEvent: false });
      return;
    }
    this.form.disable({ emitEvent: false });
  }

  private resolvePlanName(planId: number | null): string {
    if (!planId) {
      return "sem plano";
    }
    const plan = this.plans.find((item) => item.id === planId);
    return plan?.name ?? `#${planId}`;
  }

  private resolvePlanSetupFee(planId: number | null): string | null {
    if (!planId) {
      return null;
    }
    const plan = this.plans.find((item) => item.id === planId);
    return plan?.price?.setup_fee ?? null;
  }

  private normalizeSetupFee(value: string | null): string {
    if (!value) {
      return "";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "";
    }
    if (numeric === 0) {
      return "0";
    }
    if (numeric === 150) {
      return "150";
    }
    return "";
  }
}
