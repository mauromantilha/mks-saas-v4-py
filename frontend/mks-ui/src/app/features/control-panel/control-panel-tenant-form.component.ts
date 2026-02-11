import { CommonModule } from "@angular/common";
import {
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
  computed,
  inject,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import {
  catchError,
  debounceTime,
  distinctUntilChanged,
  EMPTY,
  finalize,
  switchMap,
  tap,
  throwError,
} from "rxjs";

import { PermissionService } from "../../core/auth/permission.service";
import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import {
  PlanDto,
  TenantCreateDto,
  TenantDto,
  TenantStatus,
  TenantSubscriptionUpdateDto,
  TenantUpdateDto,
} from "../../data-access/control-panel";
import { CepApi } from "../../data-access/control-panel/cep-api.service";
import { PlansApi } from "../../data-access/control-panel/plans-api.service";
import { TenantApi } from "../../data-access/control-panel/tenant-api.service";
import { normalizeAndApplyApiFormError } from "../../shared/forms/api-form-errors.util";

function onlyDigits(value: string | null | undefined): string {
  return (value || "").replace(/\D/g, "");
}

function formatCep(value: string | null | undefined): string {
  const digits = onlyDigits(value).slice(0, 8);
  if (digits.length <= 5) {
    return digits;
  }
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function formatCnpj(value: string | null | undefined): string {
  const digits = onlyDigits(value).slice(0, 14);
  if (!digits) {
    return "";
  }
  if (digits.length <= 2) {
    return digits;
  }
  if (digits.length <= 5) {
    return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  }
  if (digits.length <= 8) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  }
  if (digits.length <= 12) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function formatPhone(value: string | null | undefined): string {
  const digits = onlyDigits(value).slice(0, 11);
  if (!digits) {
    return "";
  }
  if (digits.length <= 2) {
    return `(${digits}`;
  }
  if (digits.length <= 6) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  }
  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function cepValidator(control: AbstractControl): ValidationErrors | null {
  const digits = onlyDigits(control.value);
  if (!digits) {
    return null;
  }
  return digits.length === 8 ? null : { cepInvalid: true };
}

function phoneValidator(control: AbstractControl): ValidationErrors | null {
  const digits = onlyDigits(control.value);
  if (!digits) {
    return null;
  }
  return digits.length === 10 || digits.length === 11 ? null : { phoneInvalid: true };
}

function setupFeeValidator(control: AbstractControl): ValidationErrors | null {
  const raw = String(control.value ?? "");
  if (!raw) {
    return null;
  }
  return raw === "0" || raw === "150" ? null : { setupFeeInvalid: true };
}

function cnpjValidator(control: AbstractControl): ValidationErrors | null {
  const digits = onlyDigits(control.value);
  if (!digits) {
    return null;
  }
  if (digits.length !== 14 || /^(\d)\1+$/.test(digits)) {
    return { cnpjInvalid: true };
  }

  const calcCheck = (base: string, factors: number[]) => {
    const sum = base
      .split("")
      .map((digit, idx) => Number(digit) * factors[idx])
      .reduce((acc, value) => acc + value, 0);
    const mod = sum % 11;
    return mod < 2 ? 0 : 11 - mod;
  };

  const first = calcCheck(digits.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const second = calcCheck(
    `${digits.slice(0, 12)}${first}`,
    [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
  );

  return digits.endsWith(`${first}${second}`) ? null : { cnpjInvalid: true };
}

@Component({
  selector: "app-control-panel-tenant-form",
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
    MatIconModule,
    MatProgressSpinnerModule,
    PermissionDirective,
  ],
  templateUrl: "./control-panel-tenant-form.component.html",
  styleUrl: "./control-panel-tenant-form.component.scss",
})
export class ControlPanelTenantFormComponent implements OnInit, OnChanges {
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) mode: "create" | "edit" = "create";
  @Input() tenantId: number | null = null;
  @Output() saved = new EventEmitter<TenantDto>();
  @Output() cancelled = new EventEmitter<void>();

  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly cepLoading = signal(false);
  readonly error = signal("");
  readonly plans = signal<PlanDto[]>([]);

  readonly canEditStatus = computed(
    () => this.mode === "edit" && this.permissionService.can("cp.tenants.manage")
  );

  private lastLoadKey = "";

  readonly form = new FormGroup({
    legal_name: new FormControl("", { nonNullable: true, validators: [Validators.required, Validators.minLength(3)] }),
    slug: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)],
    }),
    subdomain: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)],
    }),
    cnpj: new FormControl("", { nonNullable: true, validators: [cnpjValidator] }),
    contact_email: new FormControl("", { nonNullable: true, validators: [Validators.email] }),
    contact_phone: new FormControl("", { nonNullable: true, validators: [phoneValidator] }),
    cep: new FormControl("", { nonNullable: true, validators: [cepValidator] }),
    street: new FormControl("", { nonNullable: true }),
    number: new FormControl("", { nonNullable: true }),
    complement: new FormControl("", { nonNullable: true }),
    district: new FormControl("", { nonNullable: true }),
    city: new FormControl("", { nonNullable: true }),
    state: new FormControl("", { nonNullable: true, validators: [Validators.maxLength(2)] }),
    plan_id: new FormControl<number | null>(null, [Validators.required]),
    setup_fee_override: new FormControl("", { nonNullable: true, validators: [setupFeeValidator] }),
    is_trial: new FormControl(false, { nonNullable: true }),
    trial_days: new FormControl<number | null>(null, [Validators.min(1), Validators.max(90)]),
    is_courtesy: new FormControl(false, { nonNullable: true }),
    status: new FormControl<TenantStatus>("ACTIVE", { nonNullable: true, validators: [Validators.required] }),
  });

  constructor(
    private readonly tenantApi: TenantApi,
    private readonly plansApi: PlansApi,
    private readonly cepApi: CepApi,
    private readonly permissionService: PermissionService,
    private readonly toast: ToastService
  ) {}

  ngOnInit(): void {
    this.bindMaskHandlers();
    this.bindCepLookup();
    this.bindTrialValidation();
    this.bindPlanDefaults();
    this.loadData();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["mode"] || changes["tenantId"]) {
      this.loadData();
    }
  }

  planLabel(plan: PlanDto): string {
    const monthly = plan.price?.monthly_price ? `R$ ${plan.price.monthly_price}` : "sem preço";
    const setup = plan.price?.setup_fee ? `setup R$ ${plan.price.setup_fee}` : "setup R$ 0";
    return `${plan.name} (${plan.tier}) • ${monthly} • ${setup}`;
  }

  save(): void {
    this.error.set("");
    this.form.markAllAsTouched();

    if (this.form.invalid) {
      this.error.set("Revise os campos obrigatórios e tente novamente.");
      return;
    }

    const planId = Number(this.form.controls.plan_id.value);
    if (!Number.isFinite(planId) || planId <= 0) {
      this.error.set("Selecione um plano válido.");
      return;
    }

    const tenantPayload = this.buildTenantPayload();
    const subscriptionPayload = this.buildSubscriptionPayload(planId);

    this.saving.set(true);

    const tenantRequest$ =
      this.mode === "edit" && this.tenantId
        ? this.tenantApi.updateTenant(this.tenantId, tenantPayload as TenantUpdateDto)
        : this.tenantApi.createTenant(tenantPayload as TenantCreateDto);

    tenantRequest$
      .pipe(
        switchMap((tenant) =>
          this.plansApi
            .updateTenantSubscription(tenant.id, subscriptionPayload)
            .pipe(catchError((error) => this.handleSubscriptionSaveError(error)))
        ),
        finalize(() => this.saving.set(false))
      )
      .subscribe({
        next: (tenant) => {
          this.toast.success(
            this.mode === "edit" ? "Tenant atualizado com sucesso." : "Tenant criado com sucesso."
          );
          this.saved.emit(tenant);
        },
        error: (err) => this.handleSaveError(err),
      });
  }

  onCancel(): void {
    this.cancelled.emit();
  }

  private loadData(): void {
    const key = `${this.mode}:${this.tenantId ?? "new"}`;
    if (this.lastLoadKey === key) {
      return;
    }
    this.lastLoadKey = key;

    this.error.set("");
    this.loading.set(true);
    this.applyStatusAccessRule();
    this.resetBaseForm();

    this.plansApi
      .listPlans()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (plans) => {
          this.plans.set(plans);
          if (plans.length > 0) {
            this.form.controls.plan_id.setValue(plans[0].id);
            this.form.controls.setup_fee_override.setValue(
              String(Number(plans[0].price?.setup_fee ?? 0))
            );
          }

          if (this.mode === "edit") {
            if (!this.tenantId) {
              this.error.set("ID de tenant inválido para edição.");
              return;
            }
            this.loadTenantForEdit(this.tenantId);
          }
        },
        error: () => {
          this.error.set("Não foi possível carregar os planos.");
        },
      });
  }

  private loadTenantForEdit(tenantId: number): void {
    this.loading.set(true);
    this.tenantApi
      .getTenant(tenantId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (tenant) => {
          this.form.patchValue(
            {
              legal_name: tenant.legal_name || "",
              slug: tenant.slug || "",
              subdomain: tenant.subdomain || "",
              cnpj: formatCnpj(tenant.cnpj || ""),
              contact_email: tenant.contact_email || "",
              cep: formatCep(tenant.cep || ""),
              street: tenant.street || "",
              number: tenant.number || "",
              complement: tenant.complement || "",
              district: tenant.district || "",
              city: tenant.city || "",
              state: (tenant.state || "").toUpperCase(),
              plan_id: tenant.subscription?.plan?.id ?? this.form.controls.plan_id.value,
              setup_fee_override:
                tenant.subscription?.setup_fee_override !== null &&
                tenant.subscription?.setup_fee_override !== undefined
                  ? String(tenant.subscription.setup_fee_override)
                  : this.form.controls.setup_fee_override.value,
              is_trial: tenant.subscription?.is_trial ?? false,
              trial_days: tenant.subscription?.is_trial ? 7 : null,
              is_courtesy: tenant.subscription?.is_courtesy ?? false,
              status: tenant.status,
            },
            { emitEvent: false }
          );
          this.form.markAsPristine();
          this.applyStatusAccessRule();
        },
        error: () => {
          this.error.set("Não foi possível carregar os dados do tenant.");
        },
      });
  }

  private bindMaskHandlers(): void {
    this.form.controls.cnpj.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        const formatted = formatCnpj(value);
        if (formatted !== value) {
          this.form.controls.cnpj.setValue(formatted, { emitEvent: false });
        }
      });

    this.form.controls.cep.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        const formatted = formatCep(value);
        if (formatted !== value) {
          this.form.controls.cep.setValue(formatted, { emitEvent: false });
        }
      });

    this.form.controls.contact_phone.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        const formatted = formatPhone(value);
        if (formatted !== value) {
          this.form.controls.contact_phone.setValue(formatted, { emitEvent: false });
        }
      });

    this.form.controls.slug.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        if (!value) {
          return;
        }
        const normalized = value.toLowerCase().replace(/[^a-z0-9-]/g, "");
        if (normalized !== value) {
          this.form.controls.slug.setValue(normalized, { emitEvent: false });
        }
        if (this.mode === "create" && !this.form.controls.subdomain.dirty) {
          this.form.controls.subdomain.setValue(normalized, { emitEvent: false });
        }
      });
  }

  private bindCepLookup(): void {
    this.form.controls.cep.valueChanges
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        tap(() => this.clearCepLookupError()),
        debounceTime(300),
        distinctUntilChanged(),
        tap(() => this.cepLoading.set(false)),
        switchMap((value) => {
          const cep = onlyDigits(value);
          if (cep.length !== 8) {
            return EMPTY;
          }
          this.cepLoading.set(true);
          return this.cepApi.lookupCep(cep).pipe(
            finalize(() => this.cepLoading.set(false)),
            catchError(() => {
              this.setCepLookupError();
              this.toast.warning("CEP não encontrado. Complete o endereço manualmente.");
              return EMPTY;
            })
          );
        })
      )
      .subscribe((data) => {
        this.patchAddressControl("street", data.logradouro || "");
        this.patchAddressControl("district", data.bairro || "");
        this.patchAddressControl("city", data.cidade || "");
        this.patchAddressControl("state", (data.uf || "").toUpperCase());
      });
  }

  private bindTrialValidation(): void {
    this.form.controls.is_trial.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((isTrial) => {
        if (isTrial) {
          if (!this.form.controls.trial_days.value) {
            this.form.controls.trial_days.setValue(7);
          }
          this.form.controls.trial_days.addValidators([Validators.required]);
          this.form.controls.trial_days.updateValueAndValidity({ emitEvent: false });
          return;
        }

        this.form.controls.trial_days.removeValidators([Validators.required]);
        this.form.controls.trial_days.setValue(null);
        this.form.controls.trial_days.updateValueAndValidity({ emitEvent: false });
      });
  }

  private bindPlanDefaults(): void {
    this.form.controls.plan_id.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef), distinctUntilChanged())
      .subscribe((planId) => {
        if (!planId) {
          return;
        }
        const plan = this.findPlanById(planId);
        if (!plan || !plan.price) {
          return;
        }
        const setupControl = this.form.controls.setup_fee_override;
        if (!setupControl.dirty || !setupControl.value) {
          setupControl.setValue(String(Number(plan.price.setup_fee)), { emitEvent: false });
        }
      });
  }

  private buildTenantPayload(): TenantCreateDto | TenantUpdateDto {
    const payload: TenantCreateDto | TenantUpdateDto = {
      legal_name: this.form.controls.legal_name.value.trim(),
      slug: this.form.controls.slug.value.trim().toLowerCase(),
      subdomain: this.form.controls.subdomain.value.trim().toLowerCase(),
      cnpj: formatCnpj(this.form.controls.cnpj.value),
      contact_email: this.form.controls.contact_email.value.trim(),
      cep: formatCep(this.form.controls.cep.value),
      street: this.form.controls.street.value.trim(),
      number: this.form.controls.number.value.trim(),
      complement: this.form.controls.complement.value.trim(),
      district: this.form.controls.district.value.trim(),
      city: this.form.controls.city.value.trim(),
      state: this.form.controls.state.value.trim().toUpperCase(),
    };

    if (this.mode === "edit" && this.canEditStatus()) {
      payload.status = this.form.controls.status.value;
    }

    return payload;
  }

  private buildSubscriptionPayload(planId: number): TenantSubscriptionUpdateDto {
    const setupFee = this.form.controls.setup_fee_override.value;
    return {
      plan_id: planId,
      is_trial: this.form.controls.is_trial.value,
      trial_days: this.form.controls.is_trial.value
        ? Number(this.form.controls.trial_days.value || 7)
        : undefined,
      is_courtesy: this.form.controls.is_courtesy.value,
      setup_fee_override: setupFee ? setupFee : null,
    };
  }

  private handleSaveError(error: unknown): void {
    const message = normalizeAndApplyApiFormError(
      this.form,
      error,
      "Não foi possível salvar o tenant."
    );
    this.error.set(message);
    this.toast.error(this.error());
  }

  private handleSubscriptionSaveError(error: unknown) {
    this.error.set("Tenant salvo, mas houve falha ao atualizar assinatura.");
    this.toast.error(this.error());
    return throwError(() => error);
  }

  private patchAddressControl(
    controlName: "street" | "district" | "city" | "state",
    incomingValue: string
  ): void {
    const control = this.form.controls[controlName];
    const current = (control.value || "").trim();
    if (!incomingValue) {
      return;
    }
    if (!current || !control.dirty) {
      control.setValue(incomingValue, { emitEvent: false });
    }
  }

  private clearCepLookupError(): void {
    const control = this.form.controls.cep;
    if (!control.errors?.["lookupFailed"]) {
      return;
    }
    const { lookupFailed: _ignored, ...rest } = control.errors;
    control.setErrors(Object.keys(rest).length > 0 ? rest : null);
  }

  private setCepLookupError(): void {
    const control = this.form.controls.cep;
    control.setErrors({
      ...(control.errors ?? {}),
      lookupFailed: true,
    });
    control.markAsTouched();
  }

  private applyStatusAccessRule(): void {
    if (this.canEditStatus()) {
      this.form.controls.status.enable({ emitEvent: false });
      return;
    }
    this.form.controls.status.disable({ emitEvent: false });
    this.form.controls.status.setValue("ACTIVE", { emitEvent: false });
  }

  private resetBaseForm(): void {
    this.form.reset(
      {
        legal_name: "",
        slug: "",
        subdomain: "",
        cnpj: "",
        contact_email: "",
        contact_phone: "",
        cep: "",
        street: "",
        number: "",
        complement: "",
        district: "",
        city: "",
        state: "",
        plan_id: null,
        setup_fee_override: "",
        is_trial: false,
        trial_days: null,
        is_courtesy: false,
        status: "ACTIVE",
      },
      { emitEvent: false }
    );
    this.form.markAsPristine();
  }

  private findPlanById(planId: number): PlanDto | undefined {
    return this.plans().find((plan) => plan.id === planId);
  }
}
