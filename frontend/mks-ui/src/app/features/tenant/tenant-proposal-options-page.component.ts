import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import { OpportunityRecord, ProposalOptionRecord } from "../../core/api/sales-flow.types";
import { SessionService } from "../../core/auth/session.service";

@Component({
  selector: "app-tenant-proposal-options-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: "./tenant-proposal-options-page.component.html",
  styleUrl: "./tenant-proposal-options-page.component.scss",
})
export class TenantProposalOptionsPageComponent {
  readonly session = computed(() => this.sessionService.session());
  readonly canWrite = computed(() => {
    const role = this.session()?.role;
    return role === "OWNER" || role === "MANAGER";
  });

  loading = signal(false);
  error = signal("");
  notice = signal("");
  aiResult = signal("");

  opportunities = signal<OpportunityRecord[]>([]);
  options = signal<ProposalOptionRecord[]>([]);

  opportunity = signal<number | null>(null);
  insurerName = signal("");
  planName = signal("");
  coverageSummary = signal("");
  annualPremium = signal("");
  monthlyPremium = signal("");
  commissionPercent = signal("");
  commissionAmount = signal("");
  rankingScore = signal(0);
  isRecommended = signal(false);
  notes = signal("");

  editing = signal<ProposalOptionRecord | null>(null);
  editInsurerName = signal("");
  editPlanName = signal("");
  editCoverageSummary = signal("");
  editDeductible = signal("");
  editFranchiseNotes = signal("");
  editAnnualPremium = signal("");
  editMonthlyPremium = signal("");
  editCommissionPercent = signal("");
  editCommissionAmount = signal("");
  editRankingScore = signal(0);
  editRecommended = signal(false);
  editExternalReference = signal("");
  editNotes = signal("");

  constructor(
    private readonly salesFlowService: SalesFlowService,
    private readonly sessionService: SessionService,
    private readonly router: Router
  ) {
    if (!this.sessionService.isAuthenticated()) {
      void this.router.navigate(["/login"]);
      return;
    }
    this.bootstrap();
  }

  private parseError(err: unknown, fallback: string): string {
    const candidate = err as { error?: { detail?: unknown } };
    const detail = candidate?.error?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (detail) {
      return JSON.stringify(detail);
    }
    return fallback;
  }

  bootstrap(): void {
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");
    let done = 0;
    const markDone = () => {
      done += 1;
      if (done >= 2) {
        this.loading.set(false);
      }
    };

    this.salesFlowService.listOpportunities().subscribe({
      next: (rows) => {
        this.opportunities.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar oportunidades.");
        this.loading.set(false);
      },
    });

    this.salesFlowService.listProposalOptions().subscribe({
      next: (rows) => {
        this.options.set(rows);
        markDone();
      },
      error: () => {
        this.error.set("Erro ao carregar propostas.");
        this.loading.set(false);
      },
    });
  }

  createOption(): void {
    if (!this.canWrite()) {
      return;
    }
    if (!this.opportunity()) {
      this.error.set("Selecione uma oportunidade.");
      return;
    }
    if (!this.insurerName().trim()) {
      this.error.set("Informe a seguradora da proposta.");
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");

    this.salesFlowService
      .createProposalOption({
        opportunity: this.opportunity() as number,
        insurer_name: this.insurerName().trim(),
        plan_name: this.planName().trim() || undefined,
        coverage_summary: this.coverageSummary().trim() || undefined,
        annual_premium: this.annualPremium().trim() || null,
        monthly_premium: this.monthlyPremium().trim() || null,
        commission_percent: this.commissionPercent().trim() || null,
        commission_amount: this.commissionAmount().trim() || null,
        ranking_score: this.rankingScore(),
        is_recommended: this.isRecommended(),
        notes: this.notes().trim() || undefined,
      })
      .subscribe({
        next: () => {
          this.notice.set("Proposta criada.");
          this.insurerName.set("");
          this.planName.set("");
          this.coverageSummary.set("");
          this.annualPremium.set("");
          this.monthlyPremium.set("");
          this.commissionPercent.set("");
          this.commissionAmount.set("");
          this.rankingScore.set(0);
          this.notes.set("");
          this.isRecommended.set(false);
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao criar proposta."));
          this.loading.set(false);
        },
      });
  }

  startEdit(record: ProposalOptionRecord): void {
    this.editing.set(record);
    this.editInsurerName.set(record.insurer_name || "");
    this.editPlanName.set(record.plan_name || "");
    this.editCoverageSummary.set(record.coverage_summary || "");
    this.editDeductible.set(record.deductible || "");
    this.editFranchiseNotes.set(record.franchise_notes || "");
    this.editAnnualPremium.set(record.annual_premium ?? "");
    this.editMonthlyPremium.set(record.monthly_premium ?? "");
    this.editCommissionPercent.set(record.commission_percent ?? "");
    this.editCommissionAmount.set(record.commission_amount ?? "");
    this.editRankingScore.set(record.ranking_score ?? 0);
    this.editRecommended.set(record.is_recommended);
    this.editExternalReference.set(record.external_reference || "");
    this.editNotes.set(record.notes || "");
    this.aiResult.set("");
  }

  cancelEdit(): void {
    this.editing.set(null);
    this.aiResult.set("");
  }

  saveEdit(): void {
    const record = this.editing();
    if (!record || !this.canWrite()) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .updateProposalOption(record.id, {
        insurer_name: this.editInsurerName().trim(),
        plan_name: this.editPlanName().trim(),
        coverage_summary: this.editCoverageSummary().trim(),
        deductible: this.editDeductible().trim(),
        franchise_notes: this.editFranchiseNotes().trim(),
        annual_premium: this.editAnnualPremium().trim() || null,
        monthly_premium: this.editMonthlyPremium().trim() || null,
        commission_percent: this.editCommissionPercent().trim() || null,
        commission_amount: this.editCommissionAmount().trim() || null,
        ranking_score: this.editRankingScore(),
        is_recommended: this.editRecommended(),
        external_reference: this.editExternalReference().trim(),
        notes: this.editNotes().trim(),
      })
      .subscribe({
        next: () => {
          this.notice.set("Proposta atualizada.");
          this.cancelEdit();
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao atualizar proposta."));
          this.loading.set(false);
        },
      });
  }

  runAiInsights(): void {
    const record = this.editing();
    if (!record) {
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    this.aiResult.set("");
    this.salesFlowService
      .generateProposalOptionAIInsights(record.id, {
        focus: "proposal",
        include_cnpj_enrichment: true,
      })
      .subscribe({
        next: (resp) => {
          this.aiResult.set(JSON.stringify(resp.insights, null, 2));
          this.notice.set("Insights de IA atualizados.");
          this.bootstrap();
        },
        error: (err) => {
          this.error.set(this.parseError(err, "Erro ao gerar insights de IA."));
          this.loading.set(false);
        },
      });
  }
}
