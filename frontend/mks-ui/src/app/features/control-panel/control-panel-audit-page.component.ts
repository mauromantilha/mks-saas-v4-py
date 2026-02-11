import { CommonModule } from "@angular/common";
import { Component, DestroyRef, OnInit, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { debounceTime, distinctUntilChanged, finalize, map } from "rxjs";

import { AuditApi } from "../../data-access/control-panel/audit-api.service";
import { AuditEventDto, PaginatedResponseDto } from "../../data-access/control-panel/control-panel.dto";
import { EmptyStateComponent } from "../../shared/ui/states/empty-state.component";
import { ErrorStateComponent } from "../../shared/ui/states/error-state.component";
import { LoadingStateComponent } from "../../shared/ui/states/loading-state.component";

type PeriodValue = "1h" | "24h" | "7d" | "30d";

@Component({
  selector: "app-control-panel-audit-page",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCardModule,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: "./control-panel-audit-page.component.html",
  styleUrl: "./control-panel-audit-page.component.scss",
})
export class ControlPanelAuditPageComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  readonly displayedColumns = [
    "created_at",
    "actor",
    "action",
    "tenant",
    "entity",
    "correlation_id",
  ];

  readonly periodOptions: Array<{ value: PeriodValue; label: string }> = [
    { value: "1h", label: "Última 1h" },
    { value: "24h", label: "Últimas 24h" },
    { value: "7d", label: "Últimos 7d" },
    { value: "30d", label: "Últimos 30d" },
  ];

  readonly filtersForm = new FormGroup({
    period: new FormControl<PeriodValue>("24h", { nonNullable: true }),
    actor: new FormControl<string>("", { nonNullable: true }),
    action: new FormControl<string>("", { nonNullable: true }),
    tenantId: new FormControl<string>("", { nonNullable: true }),
    search: new FormControl<string>("", { nonNullable: true }),
  });

  readonly loading = signal(false);
  readonly error = signal("");
  readonly events = signal<AuditEventDto[]>([]);
  readonly totalRows = signal(0);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(10);

  constructor(private readonly auditApi: AuditApi) {}

  ngOnInit(): void {
    this.filtersForm.valueChanges
      .pipe(
        debounceTime(300),
        map((value) => JSON.stringify(value)),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => this.loadEvents(true));

    this.loadEvents(true);
  }

  onPageChanged(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.loadEvents();
  }

  clearFilters(): void {
    this.filtersForm.reset(
      {
        period: "24h",
        actor: "",
        action: "",
        tenantId: "",
        search: "",
      },
      { emitEvent: false }
    );
    this.loadEvents(true);
  }

  reload(): void {
    this.loadEvents();
  }

  private loadEvents(resetPage = false): void {
    if (resetPage) {
      this.pageIndex.set(0);
    }

    this.loading.set(true);
    this.error.set("");

    const raw = this.filtersForm.getRawValue();
    const range = this.periodRange(raw.period);
    const actorId = this.toNumberOrUndefined(raw.actor);
    const tenantId = this.toNumberOrUndefined(raw.tenantId);

    this.auditApi
      .listAuditEvents({
        page: this.pageIndex() + 1,
        page_size: this.pageSize(),
        period: raw.period,
        date_from: range.dateFrom,
        date_to: range.dateTo,
        actor: actorId,
        action: raw.action || "",
        tenant_id: tenantId,
        search: raw.search || "",
      })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          const normalized = this.normalizeResponse(response);
          this.events.set(normalized.results);
          this.totalRows.set(normalized.count);
        },
        error: () => {
          this.error.set("Falha ao carregar eventos de auditoria.");
          this.events.set([]);
          this.totalRows.set(0);
        },
      });
  }

  private normalizeResponse(
    response: PaginatedResponseDto<AuditEventDto> | AuditEventDto[]
  ): { results: AuditEventDto[]; count: number } {
    if (Array.isArray(response)) {
      return { results: response, count: response.length };
    }
    return {
      results: response.results ?? [],
      count: typeof response.count === "number" ? response.count : (response.results ?? []).length,
    };
  }

  private toNumberOrUndefined(value: string): number | undefined {
    if (!value) {
      return undefined;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  private periodRange(period: PeriodValue): { dateFrom: string; dateTo: string } {
    const now = new Date();
    const from = new Date(now);
    if (period === "1h") {
      from.setHours(from.getHours() - 1);
    } else if (period === "24h") {
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
