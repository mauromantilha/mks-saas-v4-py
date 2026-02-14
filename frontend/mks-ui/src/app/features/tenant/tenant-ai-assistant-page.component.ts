import { CommonModule } from "@angular/common";
import { Component, OnDestroy, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { finalize, take } from "rxjs/operators";

import { MessageService } from "primeng/api";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { ChipModule } from "primeng/chip";
import { SkeletonModule } from "primeng/skeleton";
import { TagModule } from "primeng/tag";
import { TextareaModule } from "primeng/textarea";
import { ToastModule } from "primeng/toast";

import { AiAssistantService } from "../../core/api/ai-assistant.service";
import { AiAssistantDashboardSuggestion } from "../../core/api/ai-assistant.types";
import { PermissionService } from "../../core/auth/permission.service";

interface AdvisorFeedItem {
  id: string;
  title: string;
  body: string;
  tone: "tone-green" | "tone-blue" | "tone-orange" | "tone-red";
  scope: string;
  priority: string;
}

@Component({
  selector: "app-tenant-ai-assistant-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    TextareaModule,
    ButtonModule,
    TagModule,
    ChipModule,
    SkeletonModule,
    ToastModule,
  ],
  providers: [MessageService],
  templateUrl: "./tenant-ai-assistant-page.component.html",
  styleUrl: "./tenant-ai-assistant-page.component.scss",
})
export class TenantAIAssistantPageComponent implements OnDestroy {
  readonly permissionsLoading = signal(true);
  readonly consulting = signal(false);
  readonly loadingSuggestions = signal(false);

  readonly prompt = signal("");
  readonly answer = signal("");
  readonly error = signal("");

  readonly dashboardSuggestions = signal<AiAssistantDashboardSuggestion[]>([]);
  readonly consultSuggestions = signal<string[]>([]);
  readonly lastSuggestionsAt = signal<Date | null>(null);
  readonly lastConversationId = signal<number | null>(null);
  readonly autonomousRunning = signal(true);

  readonly canUseAI = computed(() => this.permissionService.can("tenant.ai.use"));
  readonly permissionError = computed(() => this.permissionService.lastError());

  readonly analysisPills = [
    { label: "Analisando carteira", tone: "success" as const },
    { label: "Analisando receita", tone: "info" as const },
    { label: "Analisando inadimplência", tone: "danger" as const },
    { label: "Analisando sistema", tone: "warn" as const },
  ];
  readonly quickPrompts = [
    "Como está a inadimplência desta semana considerando internet e CRM?",
    "Quais oportunidades têm maior chance de fechamento neste mês?",
    "Quais clientes devo priorizar para renovação nos próximos 30 dias?",
    "Existe risco operacional no CRM que impacte meu fluxo comercial?",
  ];

  readonly advisorFeed = computed<AdvisorFeedItem[]>(() => {
    const apiRows = this.dashboardSuggestions();
    if (apiRows.length > 0) {
      return apiRows.slice(0, 6).map((row, index) => this.mapSuggestionToFeed(row, index));
    }

    const consultRows = this.consultSuggestions().map((text, index) => ({
      id: `consult-${index}`,
      title: "Sugestão do MKS Advisor",
      body: text,
      tone: "tone-blue" as const,
      scope: "advisor",
      priority: "média",
    }));

    if (consultRows.length > 0) {
      return consultRows;
    }

    return [
      {
        id: "fallback-1",
        title: "Carteira ativa",
        body: "Revise clientes com maior potencial de renovação nos próximos 30 dias.",
        tone: "tone-green",
        scope: "carteira",
        priority: "alta",
      },
      {
        id: "fallback-2",
        title: "Receita",
        body: "Monitore produção mensal versus meta para ajustar ações comerciais da semana.",
        tone: "tone-blue",
        scope: "receita",
        priority: "média",
      },
      {
        id: "fallback-3",
        title: "Inadimplência",
        body: "Priorize cobrança de parcelas vencidas acima de 15 dias para reduzir exposição.",
        tone: "tone-red",
        scope: "inadimplência",
        priority: "alta",
      },
      {
        id: "fallback-4",
        title: "Sistema",
        body: "Valide pendências operacionais abertas para evitar impacto no funil de emissão.",
        tone: "tone-orange",
        scope: "sistema",
        priority: "média",
      },
    ];
  });

  readonly suggestionsUpdatedLabel = computed(() => {
    const last = this.lastSuggestionsAt();
    if (!last) {
      return "ainda não atualizado";
    }
    const base = `atualizado às ${last.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
    return this.autonomousRunning() ? `${base} · monitor ativo` : `${base} · monitor pausado`;
  });

  private suggestionsRefreshHandle: number | null = null;

  constructor(
    private readonly aiAssistantService: AiAssistantService,
    private readonly permissionService: PermissionService,
    private readonly messageService: MessageService
  ) {
    this.bootstrap();
  }

  ngOnDestroy(): void {
    this.stopSuggestionsAutoRefresh();
  }

  sendPrompt(): void {
    if (!this.canUseAI()) {
      this.notify("warn", "Permissão", "Seu perfil não tem acesso ao MKS Advisor.");
      return;
    }

    const text = this.prompt().trim();
    if (!text) {
      this.notify("warn", "Campo obrigatório", "Digite uma pergunta para continuar.");
      return;
    }

    this.error.set("");
    this.consulting.set(true);

    this.aiAssistantService
      .consult(text, this.lastConversationId() ?? undefined)
      .pipe(finalize(() => this.consulting.set(false)))
      .subscribe({
        next: (response) => {
          this.lastConversationId.set(response.conversation_id || this.lastConversationId());
          this.answer.set(String(response.answer || "Sem resposta retornada pelo assistente."));
          this.consultSuggestions.set(
            Array.isArray(response.suggestions)
              ? response.suggestions
                  .map((item) => String(item || "").trim())
                  .filter((item) => item.length > 0)
                  .slice(0, 6)
              : []
          );
          this.prompt.set("");
          this.notify("success", "MKS Advisor", "Resposta gerada com sucesso.");
          this.refreshSuggestions(true);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || "Falha ao consultar o MKS Advisor.");
          this.notify("error", "MKS Advisor", "Não foi possível gerar a resposta.");
        },
      });
  }

  clearPrompt(): void {
    this.prompt.set("");
  }

  useQuickPrompt(prompt: string): void {
    this.prompt.set(prompt);
  }

  triggerAutonomousAnalysis(): void {
    this.refreshSuggestions();
  }

  refreshSuggestions(silent = false): void {
    if (!this.canUseAI()) {
      return;
    }

    if (!silent) {
      this.loadingSuggestions.set(true);
    }

    this.aiAssistantService
      .dashboardSuggestions()
      .pipe(
        finalize(() => {
          if (!silent) {
            this.loadingSuggestions.set(false);
          }
        })
      )
      .subscribe({
        next: (response) => {
          this.dashboardSuggestions.set(response.results || []);
          this.lastSuggestionsAt.set(new Date());
        },
        error: () => {
          if (!silent) {
            this.notify(
              "warn",
              "Sugestões",
              "Não foi possível atualizar sugestões automáticas agora."
            );
          }
        },
      });
  }

  trackByFeedId(_index: number, item: AdvisorFeedItem): string {
    return item.id;
  }

  private bootstrap(): void {
    this.permissionService.loadPermissions().pipe(take(1)).subscribe({
      next: () => {
        this.permissionsLoading.set(false);

        if (!this.canUseAI()) {
          this.error.set(
            "Acesso bloqueado: seu usuário não possui capability tenant.ai.use para usar o MKS Advisor."
          );
          return;
        }

        this.refreshSuggestions();
        this.startSuggestionsAutoRefresh();
      },
      error: () => {
        this.permissionsLoading.set(false);
        this.error.set("Falha ao validar permissões do MKS Advisor.");
        this.notify("error", "Permissões", "Não foi possível validar capabilities.");
      },
    });
  }

  private startSuggestionsAutoRefresh(): void {
    this.stopSuggestionsAutoRefresh();
    this.autonomousRunning.set(true);
    this.suggestionsRefreshHandle = window.setInterval(() => {
      if (!this.canUseAI() || document.visibilityState !== "visible") {
        return;
      }
      this.refreshSuggestions(true);
    }, 30000);
  }

  private stopSuggestionsAutoRefresh(): void {
    if (this.suggestionsRefreshHandle !== null) {
      window.clearInterval(this.suggestionsRefreshHandle);
      this.suggestionsRefreshHandle = null;
    }
    this.autonomousRunning.set(false);
  }

  private mapSuggestionToFeed(
    row: AiAssistantDashboardSuggestion,
    index: number
  ): AdvisorFeedItem {
    const title = String(row.title || "Sugestão do MKS Advisor").trim();
    const body = String(row.body || "Sem detalhes adicionais.").trim();
    const scope = String(row.scope || "advisor").toLowerCase();
    const priority = String(row.priority || row.severity || "média").toLowerCase();

    return {
      id: String(row.id || `row-${index}`),
      title,
      body,
      tone: this.resolveTone(scope, row.severity, row.priority),
      scope,
      priority,
    };
  }

  private resolveTone(
    scope: string,
    severity?: string | null,
    priority?: string | null
  ): AdvisorFeedItem["tone"] {
    const severityNorm = String(severity || "").toLowerCase();
    const priorityNorm = String(priority || "").toLowerCase();

    if (
      severityNorm.includes("critical")
      || severityNorm.includes("high")
      || priorityNorm.includes("critical")
      || priorityNorm.includes("high")
      || scope.includes("inad")
    ) {
      return "tone-red";
    }

    if (scope.includes("finance") || scope.includes("receita")) {
      return "tone-orange";
    }

    if (scope.includes("oper") || scope.includes("system")) {
      return "tone-blue";
    }

    return "tone-green";
  }

  private notify(
    severity: "success" | "info" | "warn" | "error",
    summary: string,
    detail: string
  ): void {
    this.messageService.add({ severity, summary, detail });
  }
}
