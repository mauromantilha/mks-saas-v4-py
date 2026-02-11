import { CommonModule } from "@angular/common";
import { Component, DestroyRef, Input, OnChanges, SimpleChanges, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { debounceTime, distinctUntilChanged, finalize, map } from "rxjs";

import { PermissionDirective } from "../../core/auth/permission.directive";
import { ToastService } from "../../core/ui/toast.service";
import { AuditApi } from "../../data-access/control-panel/audit-api.service";
import {
  AuditEventDto,
  PaginatedResponseDto,
  TenantFeatureFlagDto,
} from "../../data-access/control-panel/control-panel.dto";
import { TenantFeatureFlagApi } from "../../data-access/control-panel/tenant-feature-flag-api.service";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

@Component({
  selector: "app-control-panel-features-tab",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatPaginatorModule,
    MatSelectModule,
    PermissionDirective,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-features-tab.component.html",
  styleUrl: "./control-panel-features-tab.component.scss",
})
export class ControlPanelFeaturesTabComponent implements OnChanges {
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) tenantId!: number;

  readonly periodOptions: Array<{ value: "24h" | "7d" | "30d"; label: string }> = [
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
    { value: "30d", label: "Últimos 30d" },
  ];

  readonly featureColumns = [
    "feature",
    "description",
    "global_status",
    "tenant_status",
    "updated_at",
    "actions",
  ];
  readonly historyColumns = ["created_at", "action", "actor", "entity", "correlation_id"];

  readonly featuresLoading = signal(false);
  readonly featuresError = signal("");
  readonly features = signal<TenantFeatureFlagDto[]>([]);
  readonly actionLoading = signal<Record<string, boolean>>({});

  readonly auditLoading = signal(false);
  readonly auditError = signal("");
  readonly auditEvents = signal<AuditEventDto[]>([]);

  readonly filtersForm = new FormGroup({
    period: new FormControl<"24h" | "7d" | "30d">("30d", { nonNullable: true }),
    actor: new FormControl<string>("", { nonNullable: true }),
    action: new FormControl<string>("", { nonNullable: true }),
    search: new FormControl<string>("", { nonNullable: true }),
  });

  readonly filteredAuditEvents = computed(() => {
    return this.auditEvents().filter((event) => this.isFeatureEvent(event));
  });
  readonly historyPageIndex = signal(0);
  readonly historyPageSize = signal(10);
  readonly pagedAuditEvents = computed(() => {
    const start = this.historyPageIndex() * this.historyPageSize();
    return this.filteredAuditEvents().slice(start, start + this.historyPageSize());
  });

  constructor(
    private readonly featureApi: TenantFeatureFlagApi,
    private readonly auditApi: AuditApi,
    private readonly toast: ToastService
  ) {
    this.filtersForm.valueChanges
      .pipe(
        debounceTime(300),
        map((value) => JSON.stringify(value)),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => this.loadAuditHistory());
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes["tenantId"] && this.tenantId) {
      this.reload();
    }
  }

  reload(): void {
    this.loadFeatures();
    this.loadAuditHistory();
  }

  clearHistoryFilters(): void {
    this.filtersForm.reset(
      {
        period: "30d",
        actor: "",
        action: "",
        search: "",
      },
      { emitEvent: false }
    );
    this.historyPageIndex.set(0);
    this.loadAuditHistory();
  }

  onHistoryPageChanged(event: PageEvent): void {
    this.historyPageIndex.set(event.pageIndex);
    this.historyPageSize.set(event.pageSize);
  }

  toggleFeature(row: TenantFeatureFlagDto): void {
    if (!this.tenantId || !row.feature.is_active) {
      return;
    }

    const key = row.feature.key;
    this.setActionLoading(key, true);
    this.featureApi
      .updateTenantFeatureFlag(this.tenantId, {
        feature_key: key,
        enabled: !row.enabled,
      })
      .pipe(finalize(() => this.setActionLoading(key, false)))
      .subscribe({
        next: () => {
          this.toast.success(
            !row.enabled
              ? `Feature ${key} habilitada com sucesso.`
              : `Feature ${key} desabilitada com sucesso.`
          );
          this.loadFeatures();
          this.loadAuditHistory();
        },
        error: () => {
          this.toast.error("Falha ao atualizar feature flag.");
        },
      });
  }

  isToggleLoading(featureKey: string): boolean {
    return !!this.actionLoading()[featureKey];
  }

  hasFeatures(): boolean {
    return this.features().length > 0;
  }

  hasFeatureError(): boolean {
    return !this.featuresLoading() && !!this.featuresError();
  }

  hasFeatureEmpty(): boolean {
    return !this.featuresLoading() && !this.featuresError() && this.features().length === 0;
  }

  hasAuditError(): boolean {
    return !this.auditLoading() && !!this.auditError();
  }

  hasAuditEmpty(): boolean {
    return !this.auditLoading() && !this.auditError() && this.filteredAuditEvents().length === 0;
  }

  private loadFeatures(): void {
    if (!this.tenantId) {
      return;
    }

    this.featuresLoading.set(true);
    this.featuresError.set("");
    this.featureApi
      .listTenantFeatureFlags(this.tenantId)
      .pipe(finalize(() => this.featuresLoading.set(false)))
      .subscribe({
        next: (response) => {
          this.features.set(this.normalizeFeatureResponse(response));
        },
        error: () => {
          this.featuresError.set("Falha ao carregar feature flags do tenant.");
          this.features.set([]);
        },
      });
  }

  private loadAuditHistory(): void {
    if (!this.tenantId) {
      return;
    }

    const raw = this.filtersForm.getRawValue();
    const range = this.periodRange(raw.period);
    const actorId = this.toNumberOrUndefined(raw.actor);

    this.auditLoading.set(true);
    this.auditError.set("");
    this.auditApi
      .listTenantAuditEvents(this.tenantId, {
        page: 1,
        page_size: 200,
        period: raw.period,
        date_from: range.dateFrom,
        date_to: range.dateTo,
        actor: actorId,
        action: raw.action || "",
        search: raw.search || "",
      })
      .pipe(finalize(() => this.auditLoading.set(false)))
      .subscribe({
        next: (response) => {
          const events = this.normalizeAuditResponse(response);
          this.auditEvents.set(events);
          this.historyPageIndex.set(0);
        },
        error: () => {
          this.auditError.set("Falha ao carregar histórico de alterações.");
          this.auditEvents.set([]);
        },
      });
  }

  private normalizeAuditResponse(
    response: PaginatedResponseDto<AuditEventDto> | AuditEventDto[]
  ): AuditEventDto[] {
    if (Array.isArray(response)) {
      return response;
    }
    return response.results ?? [];
  }

  private normalizeFeatureResponse(
    response: PaginatedResponseDto<TenantFeatureFlagDto> | TenantFeatureFlagDto[]
  ): TenantFeatureFlagDto[] {
    if (Array.isArray(response)) {
      return response;
    }
    return response.results ?? [];
  }

  private isFeatureEvent(event: AuditEventDto): boolean {
    const action = (event.action || "").toLowerCase();
    const entityType = (event.entity_type || "").toLowerCase();
    return action.includes("feature") || entityType.includes("feature");
  }

  private setActionLoading(key: string, value: boolean): void {
    this.actionLoading.update((state) => ({ ...state, [key]: value }));
  }

  private toNumberOrUndefined(value: string): number | undefined {
    if (!value) {
      return undefined;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  private periodRange(period: "24h" | "7d" | "30d"): { dateFrom: string; dateTo: string } {
    const now = new Date();
    const from = new Date(now);
    if (period === "24h") {
      from.setDate(from.getDate() - 1);
    } else if (period === "7d") {
      from.setDate(from.getDate() - 7);
    } else {
      from.setDate(from.getDate() - 30);
    }
    return {
      dateFrom: from.toISOString(),
      dateTo: now.toISOString(),
    };
  }
}
