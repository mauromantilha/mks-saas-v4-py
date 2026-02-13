import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router } from "@angular/router";
import { finalize } from "rxjs/operators";
import { take } from "rxjs/operators";

import { MessageService } from "primeng/api";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { ChipModule } from "primeng/chip";
import { DividerModule } from "primeng/divider";
import { InputTextModule } from "primeng/inputtext";
import { ScrollPanelModule } from "primeng/scrollpanel";
import { SkeletonModule } from "primeng/skeleton";
import { TagModule } from "primeng/tag";
import { TextareaModule } from "primeng/textarea";
import { ToastModule } from "primeng/toast";

import { AiAssistantService } from "../../core/api/ai-assistant.service";
import {
  AiAssistantConsultResponse,
  AiAssistantConversationSummary,
  AiAssistantDashboardSuggestion,
  AiAssistantInternalSource,
  AiAssistantMessage,
  AiAssistantMetricUsed,
  AiAssistantWebSource,
} from "../../core/api/ai-assistant.types";
import { PermissionService } from "../../core/auth/permission.service";

interface InspectorState {
  webSources: AiAssistantWebSource[];
  internalSources: AiAssistantInternalSource[];
  metricsUsed: AiAssistantMetricUsed[];
  suggestions: string[];
}

const EMPTY_INSPECTOR: InspectorState = {
  webSources: [],
  internalSources: [],
  metricsUsed: [],
  suggestions: [],
};

@Component({
  selector: "app-tenant-ai-assistant-page",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CardModule,
    InputTextModule,
    TextareaModule,
    ButtonModule,
    ScrollPanelModule,
    DividerModule,
    TagModule,
    ChipModule,
    SkeletonModule,
    ToastModule,
  ],
  providers: [MessageService],
  templateUrl: "./tenant-ai-assistant-page.component.html",
  styleUrl: "./tenant-ai-assistant-page.component.scss",
})
export class TenantAIAssistantPageComponent {
  readonly permissionsLoading = signal(true);
  readonly loadingConversations = signal(false);
  readonly loadingConversation = signal(false);
  readonly loadingSuggestions = signal(false);
  readonly sending = signal(false);

  readonly prompt = signal("");
  readonly conversationSearch = signal("");
  readonly sourcesCollapsed = signal(false);

  readonly error = signal("");

  readonly conversations = signal<AiAssistantConversationSummary[]>([]);
  readonly messages = signal<AiAssistantMessage[]>([]);
  readonly dashboardSuggestions = signal<AiAssistantDashboardSuggestion[]>([]);

  readonly selectedConversationId = signal<number | null>(null);
  readonly selectedAssistantMessageId = signal<number | null>(null);
  readonly inspector = signal<InspectorState>(EMPTY_INSPECTOR);

  readonly canUseAI = computed(() => this.permissionService.can("tenant.ai.use"));
  readonly permissionError = computed(() => this.permissionService.lastError());

  readonly visibleConversations = computed(() => {
    const term = this.conversationSearch().trim().toLowerCase();
    if (!term) {
      return this.conversations();
    }

    return this.conversations().filter((row) => {
      const title = String(row.title || "").toLowerCase();
      const author = String(row.created_by_username || "").toLowerCase();
      return title.includes(term) || author.includes(term);
    });
  });

  readonly selectedAssistantMessage = computed(() => {
    const selectedId = this.selectedAssistantMessageId();
    if (selectedId) {
      const selected = this.messages().find(
        (msg) => msg.id === selectedId && msg.role === "assistant"
      );
      if (selected) {
        return selected;
      }
    }

    for (let idx = this.messages().length - 1; idx >= 0; idx -= 1) {
      const candidate = this.messages()[idx];
      if (candidate.role === "assistant") {
        return candidate;
      }
    }

    return null;
  });

  constructor(
    private readonly aiAssistantService: AiAssistantService,
    private readonly permissionService: PermissionService,
    private readonly messageService: MessageService,
    private readonly router: Router
  ) {
    this.bootstrap();
  }

  trackByConversationId(_index: number, row: AiAssistantConversationSummary): number {
    return row.id;
  }

  trackByMessageId(_index: number, row: AiAssistantMessage): number {
    return row.id;
  }

  trackByWebSource(_index: number, row: AiAssistantWebSource): string {
    return row.url;
  }

  trackByMetric(_index: number, row: AiAssistantMetricUsed): string {
    return `${row.key}:${row.period || "-"}`;
  }

  refreshConversations(preferredConversationId?: number): void {
    if (!this.canUseAI()) {
      return;
    }

    this.loadingConversations.set(true);
    this.aiAssistantService
      .listConversations(80)
      .pipe(finalize(() => this.loadingConversations.set(false)))
      .subscribe({
        next: (response) => {
          const rows = response.results || [];
          this.conversations.set(rows);

          const selected = this.selectedConversationId();
          const preferred =
            preferredConversationId && rows.some((item) => item.id === preferredConversationId)
              ? preferredConversationId
              : null;
          const keepCurrent =
            selected && rows.some((item) => item.id === selected) ? selected : null;
          const fallback = rows[0]?.id ?? null;
          const targetConversationId = preferred ?? keepCurrent ?? fallback;

          if (targetConversationId) {
            this.openConversation(targetConversationId);
          } else {
            this.selectedConversationId.set(null);
            this.selectedAssistantMessageId.set(null);
            this.messages.set([]);
            this.inspector.set(EMPTY_INSPECTOR);
          }
        },
        error: (err) => {
          this.error.set(err?.error?.detail || "Falha ao carregar conversas.");
          this.notify("error", "Histórico", "Não foi possível carregar conversas.");
        },
      });
  }

  openConversation(conversationId: number): void {
    if (!conversationId || !this.canUseAI()) {
      return;
    }

    this.loadingConversation.set(true);
    this.aiAssistantService
      .getConversation(conversationId)
      .pipe(finalize(() => this.loadingConversation.set(false)))
      .subscribe({
        next: (response) => {
          const rows = [...(response.conversation.messages || [])].sort(
            (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          );
          this.selectedConversationId.set(response.conversation.id);
          this.messages.set(rows);
          this.selectLatestAssistantMessage();
          this.error.set("");
        },
        error: (err) => {
          this.error.set(err?.error?.detail || "Falha ao abrir conversa.");
          this.notify("error", "Conversa", "Não foi possível abrir a conversa selecionada.");
        },
      });
  }

  sendPrompt(): void {
    if (!this.canUseAI()) {
      this.notify("warn", "Permissão", "Seu perfil não tem acesso ao IA Assistente.");
      return;
    }

    const text = this.prompt().trim();
    if (!text) {
      this.notify("warn", "Campo obrigatório", "Digite a mensagem antes de enviar.");
      return;
    }

    const conversationId = this.selectedConversationId() ?? undefined;
    this.error.set("");
    this.sending.set(true);

    this.aiAssistantService
      .consult(text, conversationId)
      .pipe(finalize(() => this.sending.set(false)))
      .subscribe({
        next: (response) => {
          this.prompt.set("");
          this.applyInspectorFromConsult(response);
          this.refreshConversations(response.conversation_id);
          this.notify("success", "IA Assistente", "Resposta gerada com sucesso.");
        },
        error: (err) => {
          this.error.set(err?.error?.detail || "Falha ao consultar IA Assistente.");
          this.notify("error", "IA Assistente", "Não foi possível gerar a resposta.");
        },
      });
  }

  selectAssistantMessage(messageId: number): void {
    this.selectedAssistantMessageId.set(messageId);
    const message = this.messages().find(
      (row) => row.id === messageId && row.role === "assistant"
    );
    if (!message) {
      this.inspector.set(EMPTY_INSPECTOR);
      return;
    }
    this.inspector.set(this.extractInspectorFromMessage(message));
  }

  useDashboardSuggestion(suggestion: AiAssistantDashboardSuggestion): void {
    const text = `${suggestion.title}. ${suggestion.body}`.trim();
    this.prompt.set(text);
  }

  openInternalSource(source: AiAssistantInternalSource): void {
    const sourceType = String(source.source_type || "").toLowerCase();
    const sourceId = String(source.source_id || "").trim();

    if (sourceType === "policy_document") {
      void this.router.navigate(["/tenant/operacional/apolices"], {
        queryParams: sourceId ? { source_id: sourceId } : undefined,
      });
      return;
    }

    if (sourceType === "special_project_document") {
      void this.router.navigate(["/tenant/comercial/projetos-especiais"], {
        queryParams: sourceId ? { source_id: sourceId } : undefined,
      });
      return;
    }

    void this.router.navigate(["/tenant/ferramentas/documentos"], {
      queryParams: {
        ...(sourceType ? { source_type: sourceType } : {}),
        ...(sourceId ? { source_id: sourceId } : {}),
      },
    });
  }

  domainFromUrl(url: string): string {
    try {
      const parsed = new URL(url);
      return parsed.hostname.replace(/^www\./i, "");
    } catch {
      return "fonte externa";
    }
  }

  roleLabel(role: AiAssistantMessage["role"]): string {
    if (role === "assistant") {
      return "Assistente";
    }
    if (role === "user") {
      return "Você";
    }
    if (role === "tool") {
      return "Tool";
    }
    return "Sistema";
  }

  roleSeverity(
    role: AiAssistantMessage["role"]
  ): "success" | "info" | "warn" | "danger" | "secondary" {
    if (role === "assistant") {
      return "success";
    }
    if (role === "user") {
      return "info";
    }
    if (role === "tool") {
      return "warn";
    }
    return "secondary";
  }

  sourceLabel(source: AiAssistantInternalSource): string {
    const preferred = String(source.document_name || source.name || "").trim();
    if (preferred) {
      return preferred;
    }
    const sourceType = String(source.source_type || "documento").replace(/_/g, " ");
    const sourceId = String(source.source_id || "-");
    return `${sourceType} #${sourceId}`;
  }

  formatMetricValue(value: string | number): string {
    if (typeof value === "number") {
      if (Number.isInteger(value)) {
        return value.toString();
      }
      return value.toFixed(2);
    }
    return String(value || "-");
  }

  private bootstrap(): void {
    this.permissionService.loadPermissions().pipe(take(1)).subscribe({
      next: () => {
        this.permissionsLoading.set(false);

        if (!this.canUseAI()) {
          this.error.set(
            "Acesso bloqueado: seu usuário não possui capability tenant.ai.use para o chat."
          );
          return;
        }

        this.refreshConversations();
        this.refreshDashboardSuggestions();
      },
      error: () => {
        this.permissionsLoading.set(false);
        this.error.set("Falha ao validar permissões do IA Assistente.");
        this.notify("error", "Permissões", "Não foi possível validar capabilities.");
      },
    });
  }

  private refreshDashboardSuggestions(): void {
    this.loadingSuggestions.set(true);
    this.aiAssistantService
      .dashboardSuggestions()
      .pipe(finalize(() => this.loadingSuggestions.set(false)))
      .subscribe({
        next: (response) => {
          this.dashboardSuggestions.set(response.results || []);
        },
        error: () => {
          this.dashboardSuggestions.set([]);
        },
      });
  }

  private selectLatestAssistantMessage(): void {
    const rows = this.messages();
    for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
      const candidate = rows[idx];
      if (candidate.role === "assistant") {
        this.selectedAssistantMessageId.set(candidate.id);
        this.inspector.set(this.extractInspectorFromMessage(candidate));
        return;
      }
    }

    this.selectedAssistantMessageId.set(null);
    this.inspector.set(EMPTY_INSPECTOR);
  }

  private applyInspectorFromConsult(response: AiAssistantConsultResponse): void {
    const web = Array.isArray(response.sources?.web) ? response.sources.web : [];
    const internal = Array.isArray(response.sources?.internal)
      ? response.sources.internal
      : [];
    const metrics = Array.isArray(response.metrics_used) ? response.metrics_used : [];
    const suggestions = Array.isArray(response.suggestions) ? response.suggestions : [];

    this.inspector.set({
      webSources: web,
      internalSources: internal,
      metricsUsed: metrics,
      suggestions,
    });
  }

  private extractInspectorFromMessage(message: AiAssistantMessage): InspectorState {
    const metadata = this.toRecord(message.metadata);
    const sources = this.toRecord(metadata["sources"]);

    return {
      webSources: this.normalizeWebSources(sources["web_sources"]),
      internalSources: this.normalizeInternalSources(sources["internal_sources"]),
      metricsUsed: this.normalizeMetrics(sources["metrics_used"]),
      suggestions: this.toStringArray(metadata["next_actions"]),
    };
  }

  private normalizeWebSources(raw: unknown): AiAssistantWebSource[] {
    const rows = Array.isArray(raw) ? raw : [];
    const output: AiAssistantWebSource[] = [];

    for (const row of rows) {
      const record = this.toRecord(row);
      const url = String(record["url"] || "").trim();
      if (!url) {
        continue;
      }
      output.push({
        url,
        title: String(record["title"] || url),
        snippet: String(record["snippet"] || ""),
      });
    }

    return output;
  }

  private normalizeInternalSources(raw: unknown): AiAssistantInternalSource[] {
    const rows = Array.isArray(raw) ? raw : [];
    const output: AiAssistantInternalSource[] = [];

    for (const row of rows) {
      const record = this.toRecord(row);
      const chunkOrderRaw = record["chunk_order"];
      const chunkOrder =
        typeof chunkOrderRaw === "number"
          ? chunkOrderRaw
          : Number.isFinite(Number(chunkOrderRaw))
            ? Number(chunkOrderRaw)
            : undefined;

      const idsRaw = Array.isArray(record["ids"]) ? record["ids"] : [];
      const ids = idsRaw
        .map((item) => Number(item))
        .filter((item) => Number.isFinite(item));

      output.push({
        name: String(record["name"] || "") || undefined,
        document_name: String(record["document_name"] || "") || undefined,
        source_type: String(record["source_type"] || "") || undefined,
        source_id: String(record["source_id"] || "") || undefined,
        chunk_order: chunkOrder,
        ids: ids.length > 0 ? ids : undefined,
      });
    }

    return output;
  }

  private normalizeMetrics(raw: unknown): AiAssistantMetricUsed[] {
    const rows = Array.isArray(raw) ? raw : [];
    const output: AiAssistantMetricUsed[] = [];

    for (const row of rows) {
      const record = this.toRecord(row);
      const key = String(record["key"] || "").trim();
      if (!key) {
        continue;
      }

      const rawValue = record["value"];
      let value: string | number = "-";
      if (typeof rawValue === "number" || typeof rawValue === "string") {
        value = rawValue;
      } else if (typeof rawValue === "boolean") {
        value = rawValue ? "true" : "false";
      }

      output.push({
        key,
        value,
        source: String(record["source"] || "") || undefined,
        period: String(record["period"] || "") || undefined,
      });
    }

    return output;
  }

  private toStringArray(raw: unknown): string[] {
    if (!Array.isArray(raw)) {
      return [];
    }
    return raw
      .map((item) => String(item || "").trim())
      .filter((item) => item.length > 0);
  }

  private toRecord(raw: unknown): Record<string, unknown> {
    if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      return raw as Record<string, unknown>;
    }
    return {};
  }

  private notify(
    severity: "success" | "info" | "warn" | "error",
    summary: string,
    detail: string
  ): void {
    this.messageService.add({ severity, summary, detail });
  }
}
