import { CommonModule } from "@angular/common";
import { Component, OnDestroy, OnInit, signal } from "@angular/core";
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { Subject, debounceTime, distinctUntilChanged, filter, takeUntil } from "rxjs";

import { PlatformTenantsService } from "../../core/api/platform-tenants.service";
import { PlanRecord, TenantStatus } from "../../core/api/platform-tenants.types";

function onlyDigits(value: string | null | undefined): string {
  return (value || "").replace(/\D/g, "");
}

function cepValidator(control: AbstractControl): ValidationErrors | null {
  const digits = onlyDigits(control.value);
  if (!digits) {
    return null;
  }
  return digits.length === 8 ? null : { cepInvalid: true };
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
  const isValid = digits.endsWith(`${first}${second}`);
  return isValid ? null : { cnpjInvalid: true };
}

function setupFeeOverrideValidator(control: AbstractControl): ValidationErrors | null {
  const raw = control.value;
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const numeric = Number(raw);
  return numeric === 0 || numeric === 150 ? null : { setupFeeInvalid: true };
}

@Component({
  selector: "app-control-panel-tenant-form-page",
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: "./control-panel-tenant-form-page.component.html",
  styleUrl: "./control-panel-tenant-form-page.component.scss",
})
export class ControlPanelTenantFormPageComponent implements OnInit, OnDestroy {
  loading = signal(false);
  saving = signal(false);
  error = signal("");
  success = signal("");
  plans = signal<PlanRecord[]>([]);
  isEdit = signal(false);
  tenantId = signal<number | null>(null);

  private readonly destroy$ = new Subject<void>();

  readonly form = new FormGroup({
    legal_name: new FormControl("", [Validators.required, Validators.minLength(3)]),
    slug: new FormControl("", [
      Validators.required,
      Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    ]),
    subdomain: new FormControl("", [
      Validators.required,
      Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    ]),
    cnpj: new FormControl("", [cnpjValidator]),
    contact_email: new FormControl("", [Validators.email]),
    cep: new FormControl("", [cepValidator]),
    street: new FormControl(""),
    number: new FormControl(""),
    complement: new FormControl(""),
    district: new FormControl(""),
    city: new FormControl(""),
    state: new FormControl("", [Validators.maxLength(2)]),
    plan_id: new FormControl<number | null>(null, [Validators.required]),
    is_trial: new FormControl(true, [Validators.required]),
    trial_days: new FormControl<number | null>(7),
    is_courtesy: new FormControl(false, [Validators.required]),
    setup_fee_override: new FormControl<number | null>(null, [setupFeeOverrideValidator]),
    status: new FormControl("ACTIVE", [Validators.required]),
  });

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly tenantsService: PlatformTenantsService
  ) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get("id"));
    if (Number.isFinite(id) && id > 0) {
      this.tenantId.set(id);
      this.isEdit.set(true);
    }

    this.form.controls.is_trial.valueChanges
      .pipe(takeUntil(this.destroy$))
      .subscribe((isTrial) => {
        if (!isTrial) {
          this.form.controls.trial_days.setValue(null);
        } else if (!this.form.controls.trial_days.value) {
          this.form.controls.trial_days.setValue(7);
        }
      });

    this.form.controls.cep.valueChanges
      .pipe(
        debounceTime(350),
        distinctUntilChanged(),
        filter(() => !this.form.controls.cep.errors),
        takeUntil(this.destroy$)
      )
      .subscribe((value) => {
        const digits = onlyDigits(value);
        if (digits.length === 8) {
          this.autoFillAddressFromCep(digits);
        }
      });

    this.loadPlansAndTenant();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadPlansAndTenant(): void {
    this.loading.set(true);
    this.error.set("");
    this.tenantsService.listPlans().subscribe({
      next: (plans) => {
        this.plans.set(plans);
        if (!this.form.controls.plan_id.value && plans.length > 0) {
          this.form.controls.plan_id.setValue(plans[0].id);
        }
        const id = this.tenantId();
        if (id) {
          this.loadTenantForEdit(id);
          return;
        }
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Não foi possível carregar planos.");
        this.loading.set(false);
      },
    });
  }

  private loadTenantForEdit(tenantId: number): void {
    this.tenantsService.getTenant(tenantId).subscribe({
      next: (tenant) => {
        this.form.patchValue({
          legal_name: tenant.legal_name,
          slug: tenant.slug,
          subdomain: tenant.subdomain,
          cnpj: tenant.cnpj || "",
          contact_email: tenant.contact_email || "",
          cep: tenant.cep || "",
          street: tenant.street || "",
          number: tenant.number || "",
          complement: tenant.complement || "",
          district: tenant.district || "",
          city: tenant.city || "",
          state: tenant.state || "",
          plan_id: tenant.subscription?.plan?.id ?? this.form.controls.plan_id.value,
          is_trial: tenant.subscription?.is_trial ?? false,
          trial_days: tenant.subscription?.is_trial ? 7 : null,
          is_courtesy: tenant.subscription?.is_courtesy ?? false,
          setup_fee_override:
            tenant.subscription?.setup_fee_override !== null
              ? Number(tenant.subscription?.setup_fee_override)
              : null,
          status: tenant.status,
        });
        this.loading.set(false);
      },
      error: () => {
        this.error.set("Não foi possível carregar tenant para edição.");
        this.loading.set(false);
      },
    });
  }

  save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.error.set("Revise os campos obrigatórios e tente novamente.");
      return;
    }

    const raw = this.form.getRawValue();
    const planId = Number(raw.plan_id);
    if (!Number.isFinite(planId) || planId <= 0) {
      this.error.set("Selecione um plano válido.");
      return;
    }
    const payload = {
      legal_name: (raw.legal_name || "").trim(),
      slug: (raw.slug || "").trim().toLowerCase(),
      subdomain: (raw.subdomain || "").trim().toLowerCase(),
      cnpj: (raw.cnpj || "").trim(),
      contact_email: (raw.contact_email || "").trim(),
      cep: onlyDigits(raw.cep || ""),
      street: (raw.street || "").trim(),
      number: (raw.number || "").trim(),
      complement: (raw.complement || "").trim(),
      district: (raw.district || "").trim(),
      city: (raw.city || "").trim(),
      state: (raw.state || "").trim().toUpperCase(),
      status: (raw.status || "ACTIVE") as TenantStatus,
      subscription: {
        plan_id: planId,
        is_trial: Boolean(raw.is_trial),
        trial_days: raw.is_trial ? Number(raw.trial_days || 7) : undefined,
        is_courtesy: Boolean(raw.is_courtesy),
        setup_fee_override:
          raw.setup_fee_override === null || raw.setup_fee_override === undefined
            ? null
            : String(raw.setup_fee_override),
      },
    };

    this.saving.set(true);
    this.error.set("");
    this.success.set("");

    const tenantId = this.tenantId();
    const request$ = tenantId
      ? this.tenantsService.patchTenant(tenantId, payload)
      : this.tenantsService.createTenant(payload);

    request$.subscribe({
      next: () => {
        this.success.set(this.isEdit() ? "Tenant atualizado com sucesso." : "Tenant criado com sucesso.");
        this.saving.set(false);
        void this.router.navigate(["/control-panel/tenants"]);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        this.error.set(detail ? JSON.stringify(detail) : "Falha ao salvar tenant.");
        this.saving.set(false);
      },
    });
  }

  private autoFillAddressFromCep(cepDigits: string): void {
    this.tenantsService.lookupCep(cepDigits).subscribe({
      next: (payload) => {
        this.form.patchValue({
          cep: payload.cep,
          street: payload.logradouro || this.form.controls.street.value,
          district: payload.bairro || this.form.controls.district.value,
          city: payload.cidade || this.form.controls.city.value,
          state: payload.uf || this.form.controls.state.value,
        });
      },
      error: () => {
        this.error.set("CEP não encontrado. Preencha o endereço manualmente.");
      },
    });
  }
}
