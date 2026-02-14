import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { Observable, forkJoin } from "rxjs";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  AIInsightResponse,
  ActivityKind,
  ActivityPriority,
  CommercialActivityRecord,
  CustomerRecord,
  LeadRecord,
  LeadHistoryRecord,
  OpportunityRecord,
  OpportunityHistoryRecord,
  OpportunityStage,
  PolicyRequestRecord,
  ProposalOptionRecord,
  SalesMetricsFilters,
  SalesMetricsRecord,
} from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";
import { PrimeUiModule } from "../../shared/prime-ui.module";

@Component({
  selector: "app-sales-flow-page",
  standalone: true,
  imports: [CommonModule, FormsModule, PrimeUiModule],
  templateUrl: "./sales-flow-page.component.html",
  styleUrl: "./sales-flow-page.component.scss",
})
export class SalesFlowPageComponent {
  private readonly brlFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");

  customers = signal<CustomerRecord[]>([]);
  leads = signal<LeadRecord[]>([]);
  opportunities = signal<OpportunityRecord[]>([]);
  policyRequests = signal<PolicyRequestRecord[]>([]);
  proposalOptions = signal<ProposalOptionRecord[]>([]);
  activities = signal<CommercialActivityRecord[]>([]);
  reminderActivities = signal<CommercialActivityRecord[]>([]);
  metrics = signal<SalesMetricsRecord | null>(null);
  leadHistory = signal<LeadHistoryRecord | null>(null);
  opportunityHistory = signal<OpportunityHistoryRecord | null>(null);
  metricsFromDate = signal("");
  metricsToDate = signal("");
  metricsAssignedTo = signal("");

  aiFocus = signal("");
  aiEntityLabel = signal("");
  aiResponse = signal<AIInsightResponse | null>(null);

  customerName = signal("");
  customerEmail = signal("");
  customerCnpj = signal("");
  customerPhone = signal("");
  customerContactName = signal("");
  customerIndustry = signal("");
  customerLeadSource = signal("");
  customerNotes = signal("");

  leadSource = signal("");
  leadFullName = signal("");
  leadCompanyName = signal("");
  leadEmail = signal("");
  leadPhone = signal("");
  leadCnpj = signal("");
  leadProductsOfInterest = signal("");
  leadEstimatedBudget = signal("");
  leadNotes = signal("");

  activityKind = signal<ActivityKind>("FOLLOW_UP");
  activityPriority = signal<ActivityPriority>("MEDIUM");
  activityTitle = signal("");
  activityDescription = signal("");
  activityDueAt = signal("");
  activityReminderAt = signal("");
  activitySlaHours = signal("");
  activityTargetType = signal<"LEAD" | "OPPORTUNITY">("LEAD");
  activityTargetId = signal("");

  proposalOpportunityId = signal("");
  proposalInsurerName = signal("");
  proposalPlanName = signal("");
  proposalAnnualPremium = signal("");
  proposalRankingScore = signal("70");
  proposalRecommended = signal(false);

  policyOpportunityId = signal("");
  policyCustomerId = signal("");
  policyIssueDeadlineAt = signal("");
  policyInspectionRequired = signal(true);
  policyNotes = signal("");

  readonly aiSummary = computed(() => this.aiResponse()?.insights.summary || "");
  readonly aiRisks = computed(() => this.aiResponse()?.insights.risks || []);
  readonly aiOpportunities = computed(
    () => this.aiResponse()?.insights.opportunities || []
  );
  readonly aiNextActions = computed(
    () => this.aiResponse()?.insights.next_actions || []
  );
  readonly aiQualificationScore = computed(
    () => this.aiResponse()?.insights.qualification_score ?? null
  );
  readonly aiProvider = computed(() => this.aiResponse()?.insights.provider || "");

  readonly activityKindOptions = [
    { label: "Task", value: "TASK" as ActivityKind },
    { label: "Follow-up", value: "FOLLOW_UP" as ActivityKind },
    { label: "Note", value: "NOTE" as ActivityKind },
  ];

  readonly activityPriorityOptions = [
    { label: "Low", value: "LOW" as ActivityPriority },
    { label: "Medium", value: "MEDIUM" as ActivityPriority },
    { label: "High", value: "HIGH" as ActivityPriority },
    { label: "Urgent", value: "URGENT" as ActivityPriority },
  ];

  readonly activityTargetTypeOptions = [
    { label: "Lead", value: "LEAD" as const },
    { label: "Oportunidade", value: "OPPORTUNITY" as const },
  ];

  readonly leadTargetOptions = computed(() =>
    this.leads().map((lead) => ({
      label: `Lead #${lead.id} - ${lead.source}`,
      value: String(lead.id),
    }))
  );

  readonly opportunityTargetOptions = computed(() =>
    this.opportunities().map((opp) => ({
      label: `Opp #${opp.id} - ${opp.title}`,
      value: String(opp.id),
    }))
  );

  readonly customerSelectOptions = computed(() =>
    this.customers().map((customer) => ({
      label: `${customer.id} - ${customer.name}`,
      value: String(customer.id),
    }))
  );

  constructor(
    private readonly salesFlowService: SalesFlowService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set("");

    forkJoin({
      customers: this.salesFlowService.listCustomers(),
      leads: this.salesFlowService.listLeads(),
      opportunities: this.salesFlowService.listOpportunities(),
      policyRequests: this.salesFlowService.listPolicyRequests(),
      proposalOptions: this.salesFlowService.listProposalOptions(),
      activities: this.salesFlowService.listActivities(),
      reminders: this.salesFlowService.listReminderActivities(),
      metrics: this.salesFlowService.getSalesMetrics(this.getMetricsFilters()),
    }).subscribe({
      next: (result) => {
        this.customers.set(result.customers);
        this.leads.set(result.leads);
        this.opportunities.set(result.opportunities);
        this.policyRequests.set(result.policyRequests);
        this.proposalOptions.set(result.proposalOptions);
        this.activities.set(result.activities);
        this.reminderActivities.set(result.reminders);
        this.metrics.set(result.metrics);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar fluxo comercial."
        );
        this.loading.set(false);
      },
    });
  }

  applyMetricsFilters(): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.getSalesMetrics(this.getMetricsFilters()).subscribe({
      next: (metrics) => {
        this.metrics.set(metrics);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(
          err?.error?.detail
            ? JSON.stringify(err.error.detail)
            : "Erro ao carregar métricas filtradas."
        );
        this.loading.set(false);
      },
    });
  }

  clearMetricsFilters(): void {
    this.metricsFromDate.set("");
    this.metricsToDate.set("");
    this.metricsAssignedTo.set("");
    this.applyMetricsFilters();
  }

  formatCurrency(value: number | null | undefined): string {
    return this.brlFormatter.format(value ?? 0);
  }

  createCustomer(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const name = this.customerName().trim();
    const email = this.customerEmail().trim();
    if (!name || !email) {
      this.error.set("Nome e email do cliente são obrigatórios.");
      return;
    }

    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .createCustomer({
        name,
        email,
        cnpj: this.customerCnpj().trim(),
        phone: this.customerPhone().trim(),
        contact_name: this.customerContactName().trim(),
        industry: this.customerIndustry().trim(),
        lead_source: this.customerLeadSource().trim(),
        notes: this.customerNotes().trim(),
        customer_type: this.customerCnpj().trim() ? "COMPANY" : "INDIVIDUAL",
        lifecycle_stage: "PROSPECT",
      })
      .subscribe({
        next: (customer) => {
          this.notice.set(`Cliente ${customer.name} criado com sucesso.`);
          this.resetCustomerForm();
          this.load();
        },
        error: (err) => this.handleActionError(err, "Erro ao criar cliente."),
      });
  }

  createLead(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const source = this.leadSource().trim();
    if (!source) {
      this.error.set("Origem do lead é obrigatória.");
      return;
    }

    const estimatedBudget = this.leadEstimatedBudget().trim();

    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .createLead({
        source,
        full_name: this.leadFullName().trim(),
        company_name: this.leadCompanyName().trim(),
        email: this.leadEmail().trim(),
        phone: this.leadPhone().trim(),
        cnpj: this.leadCnpj().trim(),
        products_of_interest: this.leadProductsOfInterest().trim(),
        estimated_budget: estimatedBudget || undefined,
        notes: this.leadNotes().trim(),
      })
      .subscribe({
        next: (lead) => {
          this.notice.set(`Lead #${lead.id} criado com sucesso.`);
          this.resetLeadForm();
          this.load();
        },
        error: (err) => this.handleActionError(err, "Erro ao criar lead."),
      });
  }

  createActivity(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const title = this.activityTitle().trim();
    if (!title) {
      this.error.set("Título da atividade é obrigatório.");
      return;
    }

    const targetId = Number.parseInt(this.activityTargetId(), 10);
    if (Number.isNaN(targetId)) {
      this.error.set("Selecione o lead ou oportunidade para vincular a atividade.");
      return;
    }

    const dueAt = this.parseLocalDateTime(this.activityDueAt());
    const reminderAt = this.parseLocalDateTime(this.activityReminderAt());
    if (this.activityReminderAt().trim() && reminderAt === null) {
      this.error.set("Data de lembrete inválida.");
      return;
    }
    if (this.activityDueAt().trim() && dueAt === null) {
      this.error.set("Data de vencimento inválida.");
      return;
    }

    const slaHoursText = this.activitySlaHours().trim();
    let slaHours: number | null = null;
    if (slaHoursText) {
      slaHours = Number.parseInt(slaHoursText, 10);
      if (!Number.isInteger(slaHours) || slaHours <= 0) {
        this.error.set("SLA deve ser um número inteiro maior que zero.");
        return;
      }
    }

    const payload = {
      kind: this.activityKind(),
      title,
      description: this.activityDescription().trim(),
      priority: this.activityPriority(),
      due_at: dueAt,
      reminder_at: reminderAt,
      sla_hours: slaHours,
      lead: this.activityTargetType() === "LEAD" ? targetId : null,
      opportunity: this.activityTargetType() === "OPPORTUNITY" ? targetId : null,
    };

    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.createActivity(payload).subscribe({
      next: () => {
        this.notice.set("Atividade criada com sucesso.");
        this.resetActivityForm();
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao criar atividade."),
    });
  }

  createProposalOption(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const opportunityId = Number.parseInt(this.proposalOpportunityId(), 10);
    if (Number.isNaN(opportunityId)) {
      this.error.set("Selecione a oportunidade da proposta.");
      return;
    }

    const insurerName = this.proposalInsurerName().trim();
    if (!insurerName) {
      this.error.set("Seguradora é obrigatória.");
      return;
    }

    const rankingScore = Number.parseInt(this.proposalRankingScore(), 10);
    if (!Number.isInteger(rankingScore) || rankingScore < 0 || rankingScore > 100) {
      this.error.set("Score da proposta deve ficar entre 0 e 100.");
      return;
    }

    const annualPremiumText = this.proposalAnnualPremium().trim();
    const payload = {
      opportunity: opportunityId,
      insurer_name: insurerName,
      plan_name: this.proposalPlanName().trim(),
      annual_premium: annualPremiumText || null,
      ranking_score: rankingScore,
      is_recommended: this.proposalRecommended(),
    };

    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.createProposalOption(payload).subscribe({
      next: () => {
        this.notice.set("Proposta comparativa cadastrada.");
        this.resetProposalForm();
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao criar proposta comparativa."),
    });
  }

  createPolicyRequest(): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    const opportunityId = Number.parseInt(this.policyOpportunityId(), 10);
    if (Number.isNaN(opportunityId)) {
      this.error.set("Selecione a oportunidade para emissão.");
      return;
    }

    const customerIdText = this.policyCustomerId().trim();
    const customerId = customerIdText ? Number.parseInt(customerIdText, 10) : null;
    if (customerIdText && Number.isNaN(customerId)) {
      this.error.set("Cliente inválido para pedido de emissão.");
      return;
    }

    const issueDeadlineAt = this.parseLocalDateTime(this.policyIssueDeadlineAt());
    if (this.policyIssueDeadlineAt().trim() && issueDeadlineAt === null) {
      this.error.set("Prazo de emissão inválido.");
      return;
    }

    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .createPolicyRequest({
        opportunity: opportunityId,
        customer: customerId ?? undefined,
        inspection_required: this.policyInspectionRequired(),
        issue_deadline_at: issueDeadlineAt,
        notes: this.policyNotes().trim(),
      })
      .subscribe({
        next: () => {
          this.notice.set("Pedido de emissão criado.");
          this.resetPolicyRequestForm();
          this.load();
        },
        error: (err) => this.handleActionError(err, "Erro ao criar pedido de emissão."),
      });
  }

  completeActivity(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.status === "DONE") {
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.completeActivity(activity.id).subscribe({
      next: () => {
        this.notice.set("Atividade concluída.");
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao concluir atividade."),
    });
  }

  reopenActivity(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.status !== "DONE") {
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.reopenActivity(activity.id).subscribe({
      next: () => {
        this.notice.set("Atividade reaberta.");
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao reabrir atividade."),
    });
  }

  markReminderSent(activity: CommercialActivityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (activity.reminder_sent) {
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.markActivityReminded(activity.id).subscribe({
      next: () => {
        this.notice.set("Lembrete marcado como enviado.");
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao marcar lembrete enviado."),
    });
  }

  generateActivityInsights(activity: CommercialActivityRecord): void {
    this.generateAI(
      `Atividade #${activity.id}`,
      this.salesFlowService.generateActivityAIInsights(
        activity.id,
        this.getInsightPayload()
      )
    );
  }

  advancePolicyRequestStatus(policyRequest: PolicyRequestRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const nextStatus = this.getNextPolicyRequestStatus(policyRequest.status);
    if (!nextStatus) {
      this.error.set("Pedido de emissão já está em status final.");
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .updatePolicyRequest(policyRequest.id, { status: nextStatus })
      .subscribe({
        next: () => {
          this.notice.set(
            `Pedido de emissão #${policyRequest.id} movido para ${nextStatus}.`
          );
          this.load();
        },
        error: (err) =>
          this.handleActionError(err, "Erro ao avançar status do pedido de emissão."),
      });
  }

  rejectPolicyRequest(policyRequest: PolicyRequestRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (policyRequest.status === "REJECTED") {
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .updatePolicyRequest(policyRequest.id, { status: "REJECTED" })
      .subscribe({
        next: () => {
          this.notice.set(`Pedido de emissão #${policyRequest.id} marcado como rejeitado.`);
          this.load();
        },
        error: (err) =>
          this.handleActionError(err, "Erro ao rejeitar pedido de emissão."),
      });
  }

  generatePolicyRequestInsights(policyRequest: PolicyRequestRecord): void {
    this.generateAI(
      `Pedido de Emissão #${policyRequest.id}`,
      this.salesFlowService.generatePolicyRequestAIInsights(
        policyRequest.id,
        this.getInsightPayload()
      )
    );
  }

  generateProposalOptionInsights(proposalOption: ProposalOptionRecord): void {
    this.generateAI(
      `Proposta #${proposalOption.id}`,
      this.salesFlowService.generateProposalOptionAIInsights(
        proposalOption.id,
        this.getInsightPayload()
      )
    );
  }

  viewLeadHistory(lead: LeadRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.getLeadHistory(lead.id).subscribe({
      next: (payload) => {
        this.leadHistory.set(payload);
        this.opportunityHistory.set(null);
        this.loading.set(false);
      },
      error: (err) => this.handleActionError(err, "Erro ao carregar histórico do lead."),
    });
  }

  viewOpportunityHistory(opportunity: OpportunityRecord): void {
    this.loading.set(true);
    this.error.set("");
    this.salesFlowService.getOpportunityHistory(opportunity.id).subscribe({
      next: (payload) => {
        this.opportunityHistory.set(payload);
        this.leadHistory.set(null);
        this.loading.set(false);
      },
      error: (err) =>
        this.handleActionError(err, "Erro ao carregar histórico da oportunidade."),
    });
  }

  clearHistory(): void {
    this.leadHistory.set(null);
    this.opportunityHistory.set(null);
  }

  onActivityTargetTypeChange(nextValue: "LEAD" | "OPPORTUNITY"): void {
    this.activityTargetType.set(nextValue);
    this.activityTargetId.set("");
  }

  qualifyLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.qualifyLead(lead.id).subscribe({
      next: () => {
        this.notice.set(`Lead #${lead.id} qualificado.`);
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao qualificar lead."),
    });
  }

  disqualifyLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.disqualifyLead(lead.id).subscribe({
      next: () => {
        this.notice.set(`Lead #${lead.id} desqualificado.`);
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao desqualificar lead."),
    });
  }

  convertLead(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService
      .convertLead(lead.id, { create_customer_if_missing: true })
      .subscribe({
        next: (payload) => {
          const customerMessage = payload.customer_created
            ? "cliente criado automaticamente"
            : "cliente existente vinculado";
          const policyMessage = payload.policy_request
            ? `pedido de emissão #${payload.policy_request.id} gerado`
            : "sem pedido de emissão automático";
          this.notice.set(
            `Lead #${lead.id} convertido (${customerMessage}; ${policyMessage}).`
          );
          this.load();
        },
        error: (err) => this.handleActionError(err, "Erro ao converter lead."),
      });
  }

  moveToNextStage(opportunity: OpportunityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    const next = this.getNextStage(opportunity.stage);
    if (!next) {
      this.error.set("Oportunidade já está em estágio final.");
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.updateOpportunityStage(opportunity.id, next).subscribe({
      next: () => {
        this.notice.set(`Oportunidade #${opportunity.id} movida para ${next}.`);
        this.load();
      },
      error: (err) =>
        this.handleActionError(err, "Erro ao avançar estágio da oportunidade."),
    });
  }

  markLost(opportunity: OpportunityRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }
    if (opportunity.stage === "LOST") {
      return;
    }
    this.loading.set(true);
    this.notice.set("");
    this.salesFlowService.updateOpportunityStage(opportunity.id, "LOST").subscribe({
      next: () => {
        this.notice.set(`Oportunidade #${opportunity.id} marcada como perdida.`);
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao marcar oportunidade como perdida."),
    });
  }

  generateLeadInsights(lead: LeadRecord): void {
    this.generateAI(
      `Lead #${lead.id}`,
      this.salesFlowService.generateLeadAIInsights(lead.id, this.getInsightPayload())
    );
  }

  generateCustomerInsights(customer: CustomerRecord): void {
    this.generateAI(
      `Cliente #${customer.id}`,
      this.salesFlowService.generateCustomerAIInsights(
        customer.id,
        this.getInsightPayload()
      )
    );
  }

  generateOpportunityInsights(opportunity: OpportunityRecord): void {
    this.generateAI(
      `Oportunidade #${opportunity.id}`,
      this.salesFlowService.generateOpportunityAIInsights(
        opportunity.id,
        this.getInsightPayload()
      )
    );
  }

  enrichLeadCnpj(lead: LeadRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.enrichLeadCnpj(lead.id).subscribe({
      next: (response) => {
        this.notice.set(
          `Enriquecimento CNPJ do Lead #${lead.id} concluído. Campos atualizados: ${
            response.updated_fields.join(", ") || "nenhum"
          }.`
        );
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao enriquecer CNPJ do lead."),
    });
  }

  enrichCustomerCnpj(customer: CustomerRecord): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.salesFlowService.enrichCustomerCnpj(customer.id).subscribe({
      next: (response) => {
        this.notice.set(
          `Enriquecimento CNPJ do Cliente #${customer.id} concluído. Campos atualizados: ${
            response.updated_fields.join(", ") || "nenhum"
          }.`
        );
        this.load();
      },
      error: (err) => this.handleActionError(err, "Erro ao enriquecer CNPJ do cliente."),
    });
  }

  clearAiResult(): void {
    this.aiEntityLabel.set("");
    this.aiResponse.set(null);
  }

  private getInsightPayload(): { focus?: string; include_cnpj_enrichment: true } {
    const focus = this.aiFocus().trim();
    if (focus) {
      return { focus, include_cnpj_enrichment: true };
    }
    return { include_cnpj_enrichment: true };
  }

  private generateAI(label: string, request$: Observable<AIInsightResponse>): void {
    if (!this.canWrite()) {
      this.error.set("Seu perfil é somente leitura.");
      return;
    }

    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    request$.subscribe({
      next: (response) => {
        this.aiEntityLabel.set(label);
        this.aiResponse.set(response);
        this.notice.set(`${label}: insights gerados com sucesso.`);
        this.loading.set(false);
      },
      error: (err) => this.handleActionError(err, `Erro ao gerar insights de ${label}.`),
    });
  }

  private getNextStage(stage: OpportunityStage): OpportunityStage | null {
    if (stage === "NEW") {
      return "QUALIFICATION";
    }
    if (stage === "QUALIFICATION") {
      return "NEEDS_ASSESSMENT";
    }
    if (stage === "NEEDS_ASSESSMENT") {
      return "QUOTATION";
    }
    if (stage === "QUOTATION") {
      return "PROPOSAL_PRESENTATION";
    }
    if (stage === "PROPOSAL_PRESENTATION") {
      return "NEGOTIATION";
    }
    if (stage === "NEGOTIATION") {
      return "WON";
    }
    return null;
  }

  private getNextPolicyRequestStatus(
    status: PolicyRequestRecord["status"]
  ): PolicyRequestRecord["status"] | null {
    if (status === "PENDING_DATA") {
      return "UNDER_REVIEW";
    }
    if (status === "UNDER_REVIEW") {
      return "READY_TO_ISSUE";
    }
    if (status === "READY_TO_ISSUE") {
      return "ISSUED";
    }
    return null;
  }

  private resetCustomerForm(): void {
    this.customerName.set("");
    this.customerEmail.set("");
    this.customerCnpj.set("");
    this.customerPhone.set("");
    this.customerContactName.set("");
    this.customerIndustry.set("");
    this.customerLeadSource.set("");
    this.customerNotes.set("");
  }

  private resetLeadForm(): void {
    this.leadSource.set("");
    this.leadFullName.set("");
    this.leadCompanyName.set("");
    this.leadEmail.set("");
    this.leadPhone.set("");
    this.leadCnpj.set("");
    this.leadProductsOfInterest.set("");
    this.leadEstimatedBudget.set("");
    this.leadNotes.set("");
  }

  private resetActivityForm(): void {
    this.activityKind.set("FOLLOW_UP");
    this.activityPriority.set("MEDIUM");
    this.activityTitle.set("");
    this.activityDescription.set("");
    this.activityDueAt.set("");
    this.activityReminderAt.set("");
    this.activitySlaHours.set("");
    this.activityTargetType.set("LEAD");
    this.activityTargetId.set("");
  }

  private resetProposalForm(): void {
    this.proposalOpportunityId.set("");
    this.proposalInsurerName.set("");
    this.proposalPlanName.set("");
    this.proposalAnnualPremium.set("");
    this.proposalRankingScore.set("70");
    this.proposalRecommended.set(false);
  }

  private resetPolicyRequestForm(): void {
    this.policyOpportunityId.set("");
    this.policyCustomerId.set("");
    this.policyIssueDeadlineAt.set("");
    this.policyInspectionRequired.set(true);
    this.policyNotes.set("");
  }

  private getMetricsFilters(): SalesMetricsFilters {
    const filters: SalesMetricsFilters = {};
    const fromDate = this.metricsFromDate().trim();
    const toDate = this.metricsToDate().trim();
    const assignedTo = this.metricsAssignedTo().trim();

    if (fromDate) {
      filters.from = fromDate;
    }
    if (toDate) {
      filters.to = toDate;
    }
    if (assignedTo) {
      filters.assigned_to = assignedTo;
    }
    return filters;
  }

  private parseLocalDateTime(localDateTime: string): string | null {
    if (!localDateTime.trim()) {
      return null;
    }
    const date = new Date(localDateTime);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    return date.toISOString();
  }

  private handleActionError(err: unknown, fallbackMessage: string): void {
    const maybeError = err as { error?: { detail?: unknown } };
    this.error.set(
      maybeError?.error?.detail
        ? JSON.stringify(maybeError.error.detail)
        : fallbackMessage
    );
    this.notice.set("");
    this.loading.set(false);
  }

  getPriorityColor(priority: ActivityPriority): string {
    switch (priority) {
      case "LOW":
        return "#10b981"; // green
      case "MEDIUM":
        return "#f59e0b"; // yellow
      case "HIGH":
        return "#f97316"; // orange
      case "URGENT":
        return "#dc2626"; // red
      default:
        return "#6b7280"; // gray
    }
  }

  getActivityKindSeverity(kind: ActivityKind): "success" | "info" | "warning" | "danger" {
    switch (kind) {
      case "TASK":
        return "info";
      case "FOLLOW_UP":
        return "warning";
      case "NOTE":
        return "success";
      default:
        return "info";
    }
  }
}
