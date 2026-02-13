import { CommonModule } from "@angular/common";
import { Component, computed, signal } from "@angular/core";
import { Router } from "@angular/router";
import { finalize } from "rxjs/operators";

import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { SkeletonModule } from "primeng/skeleton";
import { TagModule } from "primeng/tag";

import { AiAssistantService } from "../../core/api/ai-assistant.service";
import { AiAssistantDashboardSuggestion } from "../../core/api/ai-assistant.types";

interface DetailTarget {
  path: string;
  queryParams: Record<string, string>;
}

@Component({
  selector: "app-dashboard-ai-suggestions-card",
  standalone: true,
  imports: [CommonModule, CardModule, ButtonModule, TagModule, SkeletonModule],
  templateUrl: "./dashboard-ai-suggestions-card.component.html",
  styleUrl: "./dashboard-ai-suggestions-card.component.scss",
})
export class DashboardAiSuggestionsCardComponent {
  readonly loading = signal(false);
  readonly error = signal("");
  readonly suggestions = signal<AiAssistantDashboardSuggestion[]>([]);

  readonly visibleSuggestions = computed(() => this.suggestions().slice(0, 6));

  constructor(
    private readonly aiAssistantService: AiAssistantService,
    private readonly router: Router
  ) {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set("");

    this.aiAssistantService
      .dashboardSuggestions()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          const rows = Array.isArray(response.results) ? response.results : [];
          this.suggestions.set(this.rankSuggestions(rows));
        },
        error: (err) => {
          this.suggestions.set([]);
          this.error.set(err?.error?.detail || "Falha ao carregar sugestões de IA.");
        },
      });
  }

  openAIAssistant(): void {
    void this.router.navigate(["/tenant/comercial/ai-assistente"]);
  }

  hasDetailLink(item: AiAssistantDashboardSuggestion): boolean {
    return this.resolveDetailTarget(item) !== null;
  }

  openDetail(item: AiAssistantDashboardSuggestion): void {
    const target = this.resolveDetailTarget(item);
    if (!target) {
      return;
    }

    void this.router.navigate([target.path], {
      queryParams: target.queryParams,
    });
  }

  severityLabel(value: string): string {
    const normalized = (value || "normal").trim();
    return normalized || "normal";
  }

  severityTag(
    value: string
  ): "success" | "info" | "warn" | "danger" | "secondary" {
    const normalized = (value || "").trim().toLowerCase();

    if (["critical", "urgent", "high"].includes(normalized)) {
      return "danger";
    }
    if (["medium", "warning", "warn"].includes(normalized)) {
      return "warn";
    }
    if (["low", "info"].includes(normalized)) {
      return "info";
    }
    return "secondary";
  }

  priorityTag(
    value: string
  ): "success" | "info" | "warn" | "danger" | "secondary" {
    const normalized = (value || "").trim().toLowerCase();

    if (["p1", "p0", "urgent", "high"].includes(normalized)) {
      return "danger";
    }
    if (["p2", "medium"].includes(normalized)) {
      return "warn";
    }
    if (["p3", "low"].includes(normalized)) {
      return "info";
    }
    return "secondary";
  }

  private rankSuggestions(
    items: AiAssistantDashboardSuggestion[]
  ): AiAssistantDashboardSuggestion[] {
    const severityWeight = (value: string): number => {
      const normalized = (value || "").toLowerCase();
      if (["critical", "urgent", "high"].includes(normalized)) {
        return 4;
      }
      if (["medium", "warning", "warn"].includes(normalized)) {
        return 3;
      }
      if (["low", "info"].includes(normalized)) {
        return 2;
      }
      return 1;
    };

    const priorityWeight = (value: string): number => {
      const normalized = (value || "").toLowerCase();
      if (["p0", "p1", "urgent", "high"].includes(normalized)) {
        return 4;
      }
      if (["p2", "medium"].includes(normalized)) {
        return 3;
      }
      if (["p3", "low"].includes(normalized)) {
        return 2;
      }
      return 1;
    };

    return [...items].sort((a, b) => {
      const scoreA = severityWeight(a.severity) * 10 + priorityWeight(a.priority);
      const scoreB = severityWeight(b.severity) * 10 + priorityWeight(b.priority);
      if (scoreA !== scoreB) {
        return scoreB - scoreA;
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }

  private resolveDetailTarget(
    item: AiAssistantDashboardSuggestion
  ): DetailTarget | null {
    const type = (item.related_entity_type || "").trim().toLowerCase();
    const id = (item.related_entity_id || "").trim();

    if (!type || !id) {
      return null;
    }

    if (["lead", "leads"].includes(type)) {
      return {
        path: "/tenant/comercial/leads",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["customer", "customers", "client", "clients"].includes(type)) {
      return {
        path: "/tenant/comercial/clientes",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["opportunity", "opportunities"].includes(type)) {
      return {
        path: "/tenant/comercial/oportunidades",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["activity", "activities", "agenda"].includes(type)) {
      return {
        path: "/tenant/comercial/atividades",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["policy", "policies", "apolice", "apolices"].includes(type)) {
      return {
        path: "/tenant/operacional/apolices",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["insurer", "insurers", "seguradora", "seguradoras"].includes(type)) {
      return {
        path: "/tenant/operacional/seguradoras",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["proposal", "proposal_option", "proposal_options"].includes(type)) {
      return {
        path: "/tenant/operacional/propostas",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["policy_request", "policy_requests", "pedido_emissao"].includes(type)) {
      return {
        path: "/tenant/operacional/pedidos-emissao",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["invoice", "invoices", "fiscal"].includes(type)) {
      return {
        path: "/tenant/financeiro/notas-fiscais",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["payable", "payables", "installment", "installments", "finance"].includes(type)) {
      return {
        path: "/tenant/financeiro/visao-geral",
        queryParams: { entity: type, entity_id: id },
      };
    }

    if (["special_project", "special_projects", "project"].includes(type)) {
      return {
        path: "/tenant/comercial/projetos-especiais",
        queryParams: { entity: type, entity_id: id },
      };
    }

    return null;
  }
}
