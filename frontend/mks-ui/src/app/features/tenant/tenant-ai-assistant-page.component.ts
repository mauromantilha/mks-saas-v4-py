import { CommonModule } from "@angular/common";
import { Component, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";

import { SalesFlowService } from "../../core/api/sales-flow.service";
import {
  TenantAIAssistantConsultResponse,
  TenantAIAssistantInteractionRecord,
} from "../../core/api/sales-flow.types";
import { PrimeUiModule } from "../../shared/prime-ui.module";

@Component({
  selector: "app-tenant-ai-assistant-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PrimeUiModule,
  ],
  templateUrl: "./tenant-ai-assistant-page.component.html",
  styleUrl: "./tenant-ai-assistant-page.component.scss",
})
export class TenantAIAssistantPageComponent {
  loading = signal(false);
  loadingHistory = signal(false);
  error = signal("");
  notice = signal("");

  prompt = signal("");
  focus = signal("carteira, inadimplência, financeiro, equipe e metas");
  cnpj = signal("");
  learnedNote = signal("");
  pinLearning = signal(false);
  includeCnpj = signal(true);
  includeMarketResearch = signal(true);
  includeFinancialContext = signal(true);
  includeCommercialContext = signal(true);

  latestResponse = signal<TenantAIAssistantConsultResponse | null>(null);
  history = signal<TenantAIAssistantInteractionRecord[]>([]);

  constructor(private readonly salesFlowService: SalesFlowService) {
    this.loadHistory();
  }

  loadHistory(): void {
    this.loadingHistory.set(true);
    this.salesFlowService.listTenantAIAssistantInteractions(20).subscribe({
      next: (res) => {
        this.history.set(res.results || []);
        this.loadingHistory.set(false);
      },
      error: (err) => {
        this.loadingHistory.set(false);
        this.error.set(err?.error?.detail || "Falha ao carregar histórico do assistente.");
      },
    });
  }

  consult(): void {
    const text = this.prompt().trim();
    if (!text) {
      this.error.set("Informe a pergunta para o assistente.");
      return;
    }
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");

    this.salesFlowService
      .consultTenantAIAssistant({
        prompt: text,
        focus: this.focus().trim(),
        cnpj: this.cnpj().trim(),
        include_cnpj_enrichment: this.includeCnpj(),
        include_market_research: this.includeMarketResearch(),
        include_financial_context: this.includeFinancialContext(),
        include_commercial_context: this.includeCommercialContext(),
        learned_note: this.learnedNote().trim(),
        pin_learning: this.pinLearning(),
      })
      .subscribe({
        next: (res) => {
          this.latestResponse.set(res);
          this.notice.set("Análise IA gerada com sucesso.");
          this.prompt.set("");
          this.learnedNote.set("");
          this.pinLearning.set(false);
          this.loading.set(false);
          this.loadHistory();
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail || "Falha ao consultar IA Assistente.");
        },
      });
  }

  useHistory(item: TenantAIAssistantInteractionRecord): void {
    this.latestResponse.set({
      tenant_code: "",
      interaction: item,
      assistant: item.response_payload,
      context_snapshot: item.context_snapshot || {},
      learning_memory: {
        pinned_learning: [],
        recent_interactions: [],
      },
    });
  }
}
