import { CommonModule } from "@angular/common";
import { Component, DestroyRef, OnDestroy, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from "@angular/forms";
import { Router } from "@angular/router";
import { forkJoin } from "rxjs";
import { finalize, switchMap, take } from "rxjs/operators";

import { MessageService } from "primeng/api";
import { AutoCompleteModule, AutoCompleteCompleteEvent } from "primeng/autocomplete";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { DatePickerModule } from "primeng/datepicker";
import { DialogModule } from "primeng/dialog";
import { InputTextModule } from "primeng/inputtext";
import { SelectModule } from "primeng/select";
import { SkeletonModule } from "primeng/skeleton";
import { TableModule } from "primeng/table";
import { TagModule } from "primeng/tag";
import { TextareaModule } from "primeng/textarea";
import { ToastModule } from "primeng/toast";
import { ToggleSwitchModule } from "primeng/toggleswitch";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  CustomerRecord,
  LeadRecord,
  OpportunityRecord,
  SpecialProjectRecord,
} from "../../core/api/sales-flow.types";
import {
  AgendaEventRecord,
  CreateAgendaPayload,
  SalesFlowActivityPriority,
  SalesFlowActivityType,
  SalesFlowOrigin,
  SalesFlowSummaryResponse,
  TenantSalesFlowService,
} from "../../core/api/tenant-sales-flow.service";
import { PermissionService } from "../../core/auth/permission.service";
import { SessionService } from "../../core/auth/session.service";

interface RelatedEntityOption {
  id: number;
  origin: SalesFlowOrigin;
  label: string;
}

interface KpiCard {
  label: string;
  icon: string;
  value: string;
}

@Component({
  selector: "app-tenant-sales-flow-page",
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    CardModule,
    ButtonModule,
    SkeletonModule,
    SelectModule,
    AutoCompleteModule,
    DatePickerModule,
    InputTextModule,
    TextareaModule,
    ToggleSwitchModule,
    TableModule,
    TagModule,
    DialogModule,
    ToastModule,
  ],
  providers: [MessageService],
  templateUrl: "./tenant-sales-flow-page.component.html",
  styleUrl: "./tenant-sales-flow-page.component.scss",
})
export class TenantSalesFlowPageComponent implements OnDestroy {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  private readonly pctFormatter = new Intl.NumberFormat("pt-BR", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  private readonly destroyRef = inject(DestroyRef);
  private readonly reminderQueue: AgendaEventRecord[] = [];
  private readonly queuedReminderIds = new Set<number>();
  private pollingTimer: ReturnType<typeof setInterval> | null = null;
  private reminderPollInFlight = false;

  readonly session = computed(() => this.sessionService.session());
  readonly permissionsLoading = signal(true);
  readonly loadingSummary = signal(true);
  readonly loadingEntities = signal(true);
  readonly loadingAgenda = signal(true);
  readonly savingActivity = signal(false);
  readonly savingAgenda = signal(false);
  readonly handlingReminderAction = signal(false);

  readonly summary = signal<SalesFlowSummaryResponse | null>(null);
  readonly agendaItems = signal<AgendaEventRecord[]>([]);

  readonly leads = signal<LeadRecord[]>([]);
  readonly opportunities = signal<OpportunityRecord[]>([]);
  readonly projects = signal<SpecialProjectRecord[]>([]);
  readonly customers = signal<CustomerRecord[]>([]);

  readonly targetSuggestions = signal<RelatedEntityOption[]>([]);

  readonly reminderDialogVisible = signal(false);
  readonly reminderInFocus = signal<AgendaEventRecord | null>(null);

  readonly canReadSalesFlow = computed(
    () =>
      this.permissionService.can("tenant.sales_flow.read")
      || this.permissionService.can("tenant.activities.view")
      || this.permissionService.can("activities.list")
      || this.permissionService.can("metrics.list")
  );

  readonly canManageActivities = computed(
    () =>
      this.permissionService.can("tenant.activities.manage")
      || this.permissionService.can("activities.create")
      || this.permissionService.can("activities.write")
  );

  readonly canManageAgenda = computed(
    () =>
      this.permissionService.can("tenant.agenda.manage")
      || this.permissionService.can("tenant.activities.manage")
      || this.permissionService.can("activities.create")
  );

  readonly permissionError = computed(() => this.permissionService.lastError());

  readonly kpiCards = computed<KpiCard[]>(() => {
    const summary = this.summary();
    if (!summary) {
      return [];
    }

    return [
      {
        label: "Leads novos",
        icon: "pi pi-user-plus",
        value: String(summary.leads_new),
      },
      {
        label: "Leads qualificados",
        icon: "pi pi-filter",
        value: String(summary.leads_qualified),
      },
      {
        label: "Leads convertidos",
        icon: "pi pi-check-circle",
        value: String(summary.leads_converted),
      },
      {
        label: "Oportunidades ganhas",
        icon: "pi pi-trophy",
        value: String(summary.opportunities_won),
      },
      {
        label: "Winrate",
        icon: "pi pi-percentage",
        value: this.pctFormatter.format(summary.winrate || 0),
      },
      {
        label: "Pipeline aberto",
        icon: "pi pi-wallet",
        value: this.brlFormatter.format(summary.pipeline_open || 0),
      },
      {
        label: "Atividades abertas",
        icon: "pi pi-calendar",
        value: String(summary.activities_open),
      },
      {
        label: "Atividades atrasadas",
        icon: "pi pi-exclamation-triangle",
        value: String(summary.activities_overdue),
      },
    ];
  });

  readonly activityTypeOptions: Array<{
    label: string;
    value: SalesFlowActivityType;
  }> = [
    { label: "Tarefa", value: "TASK" },
    { label: "Follow-up", value: "FOLLOW_UP" },
    { label: "Nota", value: "NOTE" },
    { label: "Reunião", value: "MEETING" },
  ];

  readonly activityPriorityOptions: Array<{
    label: string;
    value: SalesFlowActivityPriority;
  }> = [
    { label: "Baixa", value: "LOW" },
    { label: "Média", value: "MEDIUM" },
    { label: "Alta", value: "HIGH" },
    { label: "Urgente", value: "URGENT" },
  ];

  readonly originOptions: Array<{ label: string; value: SalesFlowOrigin }> = [
    { label: "Lead", value: "LEAD" },
    { label: "Oportunidade", value: "OPPORTUNITY" },
    { label: "Projeto", value: "PROJECT" },
    { label: "Cliente", value: "CUSTOMER" },
  ];

  readonly activityForm = new FormGroup({
    type: new FormControl<SalesFlowActivityType>("FOLLOW_UP", { nonNullable: true }),
    priority: new FormControl<SalesFlowActivityPriority>("MEDIUM", { nonNullable: true }),
    origin: new FormControl<SalesFlowOrigin>("LEAD", { nonNullable: true }),
    target: new FormControl<RelatedEntityOption | null>(null, {
      validators: [Validators.required],
    }),
    startAt: new FormControl<Date | null>(null, {
      validators: [Validators.required],
    }),
    endAt: new FormControl<Date | null>(null),
    title: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255)],
    }),
    note: new FormControl("", { nonNullable: true }),
  });

  readonly agendaForm = new FormGroup({
    title: new FormControl("", {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255)],
    }),
    date: new FormControl<Date | null>(null, {
      validators: [Validators.required],
    }),
    time: new FormControl("09:00", {
      nonNullable: true,
      validators: [Validators.required],
    }),
    attendeeName: new FormControl("", { nonNullable: true }),
    attendeeEmail: new FormControl("", {
      nonNullable: true,
      validators: [Validators.email],
    }),
    subject: new FormControl("", { nonNullable: true }),
    sendInvite: new FormControl(false, { nonNullable: true }),
  });

  constructor(
    private readonly tenantSalesFlowService: TenantSalesFlowService,
    private readonly salesFlowService: SalesFlowService,
    private readonly permissionService: PermissionService,
    private readonly sessionService: SessionService,
    private readonly messageService: MessageService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }

    this.activityForm.controls.origin.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((origin) => {
        this.activityForm.controls.target.setValue(null);
        this.targetSuggestions.set(this.buildTargetOptions(origin || "LEAD"));
      });

    this.bootstrap();
  }

  ngOnDestroy(): void {
    this.stopRemindersPolling();
  }

  refreshPage(): void {
    this.loadSummary();
    this.loadAgenda();
    this.loadEntities();
  }

  targetPlaceholder(): string {
    const origin = this.activityForm.controls.origin.value;
    if (origin === "LEAD") {
      return "Buscar lead por nome, empresa ou origem";
    }
    if (origin === "OPPORTUNITY") {
      return "Buscar oportunidade por título";
    }
    if (origin === "PROJECT") {
      return "Buscar projeto especial";
    }
    return "Buscar cliente por nome";
  }

  onTargetSearch(event: AutoCompleteCompleteEvent): void {
    const query = String(event.query || "").trim().toLowerCase();
    const origin = this.activityForm.controls.origin.value;
    const options = this.buildTargetOptions(origin);
    if (!query) {
      this.targetSuggestions.set(options);
      return;
    }
    this.targetSuggestions.set(
      options.filter((option) => option.label.toLowerCase().includes(query))
    );
  }

  submitActivity(): void {
    if (!this.canManageActivities()) {
      this.notify("warn", "Permissão", "Seu perfil não pode criar atividades.");
      return;
    }

    if (this.activityForm.invalid) {
      this.activityForm.markAllAsTouched();
      this.notify("warn", "Campos obrigatórios", "Preencha os campos da atividade.");
      return;
    }

    const form = this.activityForm.getRawValue();
    const startAt = form.startAt;
    if (!startAt) {
      this.notify("warn", "Data inválida", "Informe a data inicial da atividade.");
      return;
    }

    const endAt = form.endAt;
    if (endAt && endAt < startAt) {
      this.notify("warn", "Período inválido", "A data final deve ser maior que a inicial.");
      return;
    }

    const target = form.target;
    if (!target || target.origin !== form.origin) {
      this.notify("warn", "Vínculo obrigatório", "Selecione o vínculo da atividade.");
      return;
    }

    const reminderAt = new Date(startAt.getTime() - 30 * 60 * 1000).toISOString();
    const startedAt = startAt.toISOString();
    const endedAt = endAt ? endAt.toISOString() : null;

    this.savingActivity.set(true);

    if (form.origin === "LEAD" || form.origin === "OPPORTUNITY") {
      this.tenantSalesFlowService
        .createActivity({
          kind: form.type,
          title: form.title.trim(),
          description: form.note.trim(),
          priority: form.priority,
          due_at: startedAt,
          reminder_at: reminderAt,
          started_at: startedAt,
          ended_at: endedAt,
          lead: form.origin === "LEAD" ? target.id : null,
          opportunity: form.origin === "OPPORTUNITY" ? target.id : null,
        })
        .pipe(finalize(() => this.savingActivity.set(false)))
        .subscribe({
          next: () => {
            this.notify("success", "Atividade", "Atividade criada com sucesso.");
            this.activityForm.patchValue({
              title: "",
              note: "",
              startAt: null,
              endAt: null,
            });
            this.loadSummary();
            this.loadAgenda();
          },
          error: (err) => {
            this.notify(
              "error",
              "Atividade",
              err?.error?.detail || "Não foi possível criar a atividade."
            );
          },
        });
      return;
    }

    const agendaPayload: CreateAgendaPayload = {
      title: form.title.trim(),
      subject: form.note.trim(),
      start_at: startedAt,
      end_at: endedAt,
      send_invite: false,
      priority: form.priority,
      ...(form.origin === "PROJECT" ? { project: target.id } : { customer: target.id }),
    };

    this.tenantSalesFlowService
      .createAgenda(agendaPayload)
      .pipe(finalize(() => this.savingActivity.set(false)))
      .subscribe({
        next: () => {
          this.notify(
            "success",
            "Atividade",
            "Registro criado na agenda para manter compatibilidade com origem selecionada."
          );
          this.activityForm.patchValue({
            title: "",
            note: "",
            startAt: null,
            endAt: null,
          });
          this.loadSummary();
          this.loadAgenda();
        },
        error: (err) => {
          this.notify(
            "error",
            "Atividade",
            err?.error?.detail || "Não foi possível criar o registro da atividade."
          );
        },
      });
  }

  submitAgenda(): void {
    if (!this.canManageAgenda()) {
      this.notify("warn", "Permissão", "Seu perfil não pode criar compromissos.");
      return;
    }

    if (this.agendaForm.invalid) {
      this.agendaForm.markAllAsTouched();
      this.notify("warn", "Campos obrigatórios", "Preencha os campos da agenda.");
      return;
    }

    const form = this.agendaForm.getRawValue();
    const startAt = this.combineDateAndTime(form.date, form.time);
    if (!startAt) {
      this.notify("warn", "Data/Hora", "Data ou hora da agenda inválida.");
      return;
    }

    const relation = this.resolveAgendaRelation();
    if (!relation) {
      this.notify(
        "warn",
        "Vínculo obrigatório",
        "Selecione origem e vínculo na seção Criar atividade para associar a agenda."
      );
      return;
    }

    const endAt = new Date(startAt.getTime() + 60 * 60 * 1000);

    this.savingAgenda.set(true);
    this.tenantSalesFlowService
      .createAgenda({
        title: form.title.trim(),
        subject: form.subject.trim(),
        start_at: startAt.toISOString(),
        end_at: endAt.toISOString(),
        attendee_name: form.attendeeName.trim(),
        attendee_email: form.attendeeEmail.trim(),
        send_invite: form.sendInvite,
        ...relation,
      })
      .pipe(finalize(() => this.savingAgenda.set(false)))
      .subscribe({
        next: () => {
          this.notify("success", "Agenda", "Compromisso criado com sucesso.");
          this.agendaForm.patchValue({
            title: "",
            date: null,
            time: "09:00",
            subject: "",
            sendInvite: false,
          });
          this.loadSummary();
          this.loadAgenda();
        },
        error: (err) => {
          this.notify(
            "error",
            "Agenda",
            err?.error?.detail || "Não foi possível criar o compromisso."
          );
        },
      });
  }

  confirmAgenda(event: AgendaEventRecord): void {
    if (!this.canManageAgenda()) {
      return;
    }
    this.tenantSalesFlowService.confirmAgenda(event.id).subscribe({
      next: () => {
        this.notify("success", "Agenda", "Compromisso confirmado.");
        this.loadSummary();
        this.loadAgenda();
      },
      error: (err) => {
        this.notify(
          "error",
          "Agenda",
          err?.error?.detail || "Não foi possível confirmar o compromisso."
        );
      },
    });
  }

  cancelAgenda(event: AgendaEventRecord): void {
    if (!this.canManageAgenda()) {
      return;
    }
    this.tenantSalesFlowService.cancelAgenda(event.id).subscribe({
      next: () => {
        this.notify("success", "Agenda", "Compromisso cancelado.");
        this.loadSummary();
        this.loadAgenda();
      },
      error: (err) => {
        this.notify(
          "error",
          "Agenda",
          err?.error?.detail || "Não foi possível cancelar o compromisso."
        );
      },
    });
  }

  handleReminderConfirm(): void {
    this.processReminderAction("confirm");
  }

  handleReminderCancel(): void {
    this.processReminderAction("cancel");
  }

  statusLabel(status: string): string {
    if (status === "OPEN" || status === "PENDING") {
      return "Aberto";
    }
    if (status === "CONFIRMED") {
      return "Confirmado";
    }
    if (status === "CANCELED") {
      return "Cancelado";
    }
    if (status === "COMPLETED" || status === "DONE") {
      return "Concluído";
    }
    return status;
  }

  statusSeverity(
    status: string
  ): "success" | "info" | "warn" | "danger" | "secondary" {
    if (status === "CONFIRMED") {
      return "success";
    }
    if (status === "OPEN" || status === "PENDING") {
      return "info";
    }
    if (status === "CANCELED") {
      return "danger";
    }
    return "secondary";
  }

  trackByAgendaId(_index: number, row: AgendaEventRecord): number {
    return row.id;
  }

  private bootstrap(): void {
    this.permissionService
      .loadPermissions()
      .pipe(take(1))
      .subscribe({
        next: () => {
          this.permissionsLoading.set(false);
          this.loadSummary();
          this.loadEntities();
          this.loadAgenda();
          this.startRemindersPolling();
        },
        error: () => {
          this.permissionsLoading.set(false);
          this.loadSummary();
          this.loadEntities();
          this.loadAgenda();
          this.startRemindersPolling();
        },
      });
  }

  private loadSummary(): void {
    this.loadingSummary.set(true);
    this.tenantSalesFlowService
      .getSummary()
      .pipe(finalize(() => this.loadingSummary.set(false)))
      .subscribe({
        next: (response) => {
          this.summary.set(response);
        },
        error: (err) => {
          this.summary.set(null);
          this.notify(
            "error",
            "Resumo do fluxo",
            err?.error?.detail || "Não foi possível carregar os indicadores."
          );
        },
      });
  }

  private loadEntities(): void {
    this.loadingEntities.set(true);
    forkJoin({
      leads: this.salesFlowService.listLeads(),
      opportunities: this.salesFlowService.listOpportunities(),
      projects: this.salesFlowService.listSpecialProjects(),
      customers: this.salesFlowService.listCustomers(),
    })
      .pipe(finalize(() => this.loadingEntities.set(false)))
      .subscribe({
        next: ({ leads, opportunities, projects, customers }) => {
          this.leads.set(leads);
          this.opportunities.set(opportunities);
          this.projects.set(projects);
          this.customers.set(customers);
          this.targetSuggestions.set(
            this.buildTargetOptions(this.activityForm.controls.origin.value)
          );
        },
        error: (err) => {
          this.notify(
            "error",
            "Cadastros",
            err?.error?.detail || "Falha ao carregar entidades de vínculo."
          );
        },
      });
  }

  private loadAgenda(): void {
    this.loadingAgenda.set(true);

    const now = new Date();
    const future = new Date(now.getTime() + 45 * 24 * 60 * 60 * 1000);

    this.tenantSalesFlowService
      .listAgenda({
        date_from: this.toIsoDate(now),
        date_to: this.toIsoDate(future),
      })
      .pipe(finalize(() => this.loadingAgenda.set(false)))
      .subscribe({
        next: (items) => {
          this.agendaItems.set(
            [...items].sort((a, b) => {
              const left = new Date(a.start_at || a.created_at).getTime();
              const right = new Date(b.start_at || b.created_at).getTime();
              return left - right;
            })
          );
        },
        error: (err) => {
          this.notify(
            "error",
            "Agenda",
            err?.error?.detail || "Não foi possível carregar a agenda."
          );
        },
      });
  }

  private startRemindersPolling(): void {
    this.stopRemindersPolling();
    this.pollReminders(false);
    this.pollingTimer = setInterval(() => this.pollReminders(), 60000);
  }

  private stopRemindersPolling(): void {
    if (!this.pollingTimer) {
      return;
    }
    clearInterval(this.pollingTimer);
    this.pollingTimer = null;
  }

  private pollReminders(notifyIfAny = true): void {
    if (!this.canManageAgenda() || this.reminderPollInFlight) {
      return;
    }

    this.reminderPollInFlight = true;
    this.tenantSalesFlowService
      .listAgendaReminders()
      .pipe(finalize(() => {
        this.reminderPollInFlight = false;
      }))
      .subscribe({
        next: (rows) => {
          let newRows = 0;
          for (const row of rows) {
            if (this.queuedReminderIds.has(row.id)) {
              continue;
            }
            this.queuedReminderIds.add(row.id);
            this.reminderQueue.push(row);
            newRows += 1;
          }

          if (newRows > 0 && notifyIfAny) {
            this.notify("info", "Agenda", `${newRows} lembrete(s) pendente(s) detectado(s).`);
          }

          this.openNextReminderDialog();
        },
        error: () => {
          // Polling is best-effort. Errors should not flood the user with toasts.
        },
      });
  }

  private openNextReminderDialog(): void {
    if (this.reminderDialogVisible()) {
      return;
    }

    const next = this.reminderQueue.shift();
    if (!next) {
      return;
    }

    this.reminderInFocus.set(next);
    this.reminderDialogVisible.set(true);
  }

  private processReminderAction(action: "confirm" | "cancel"): void {
    const reminder = this.reminderInFocus();
    if (!reminder) {
      return;
    }

    this.handlingReminderAction.set(true);

    const action$ =
      action === "confirm"
        ? this.tenantSalesFlowService.confirmAgenda(reminder.id)
        : this.tenantSalesFlowService.cancelAgenda(reminder.id);

    action$
      .pipe(
        switchMap(() => this.tenantSalesFlowService.ackAgendaReminder(reminder.id)),
        finalize(() => this.handlingReminderAction.set(false))
      )
      .subscribe({
        next: () => {
          this.notify(
            "success",
            "Lembrete",
            action === "confirm"
              ? "Compromisso confirmado e lembrete reconhecido."
              : "Compromisso cancelado e lembrete reconhecido."
          );
          this.queuedReminderIds.delete(reminder.id);
          this.reminderInFocus.set(null);
          this.reminderDialogVisible.set(false);
          this.loadSummary();
          this.loadAgenda();
          this.openNextReminderDialog();
        },
        error: (err) => {
          this.notify(
            "error",
            "Lembrete",
            err?.error?.detail || "Não foi possível processar o lembrete."
          );
        },
      });
  }

  private resolveAgendaRelation():
    | { lead: number }
    | { opportunity: number }
    | { project: number }
    | { customer: number }
    | null {
    const target = this.activityForm.controls.target.value;
    if (!target) {
      return null;
    }

    if (target.origin === "LEAD") {
      return { lead: target.id };
    }
    if (target.origin === "OPPORTUNITY") {
      return { opportunity: target.id };
    }
    if (target.origin === "PROJECT") {
      return { project: target.id };
    }
    return { customer: target.id };
  }

  private buildTargetOptions(origin: SalesFlowOrigin): RelatedEntityOption[] {
    if (origin === "LEAD") {
      return this.leads().map((lead) => {
        const label = [lead.company_name, lead.full_name, lead.source]
          .filter((part) => String(part || "").trim().length > 0)
          .join(" - ");
        return {
          id: lead.id,
          origin,
          label: `${label || "Lead"} (#${lead.id})`,
        };
      });
    }

    if (origin === "OPPORTUNITY") {
      return this.opportunities().map((opportunity) => ({
        id: opportunity.id,
        origin,
        label: `${opportunity.title} (#${opportunity.id})`,
      }));
    }

    if (origin === "PROJECT") {
      return this.projects().map((project) => ({
        id: project.id,
        origin,
        label: `${project.name} (#${project.id})`,
      }));
    }

    return this.customers().map((customer) => ({
      id: customer.id,
      origin,
      label: `${customer.name} (#${customer.id})`,
    }));
  }

  private combineDateAndTime(date: Date | null, timeText: string): Date | null {
    if (!date) {
      return null;
    }

    const value = String(timeText || "").trim();
    const [hoursRaw, minutesRaw] = value.split(":");
    const hours = Number.parseInt(hoursRaw || "", 10);
    const minutes = Number.parseInt(minutesRaw || "", 10);

    if (!Number.isInteger(hours) || !Number.isInteger(minutes)) {
      return null;
    }
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      return null;
    }

    const result = new Date(date);
    result.setHours(hours, minutes, 0, 0);
    return result;
  }

  private toIsoDate(input: Date): string {
    return input.toISOString().slice(0, 10);
  }

  private notify(
    severity: "success" | "info" | "warn" | "error",
    summary: string,
    detail: string
  ): void {
    this.messageService.add({
      severity,
      summary,
      detail,
      life: 4000,
    });
  }
}
