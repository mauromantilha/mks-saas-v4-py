export type AiAssistantMessageRole = "user" | "assistant" | "system" | "tool";

export interface AiAssistantWebSource {
  url: string;
  title: string;
  snippet: string;
}

export interface AiAssistantInternalSource {
  name?: string;
  document_name?: string;
  source_type?: string;
  source_id?: string;
  chunk_order?: number;
  ids?: number[];
}

export interface AiAssistantMetricUsed {
  key: string;
  value: string | number;
  source?: string;
  period?: string;
}

export interface AiAssistantConsultResponse {
  conversation_id: number;
  answer: string;
  sources: {
    web: AiAssistantWebSource[];
    internal: AiAssistantInternalSource[];
  };
  metrics_used: AiAssistantMetricUsed[];
  suggestions: string[];
  intents?: string[];
  correlation_id?: string;
}

export interface AiAssistantConversationSummary {
  id: number;
  title: string | null;
  status: "open" | "closed";
  created_by: number | null;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export interface AiAssistantMessage {
  id: number;
  conversation: number;
  role: AiAssistantMessageRole;
  content: string;
  intent: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface AiAssistantConversationDetail extends AiAssistantConversationSummary {
  messages: AiAssistantMessage[];
}

export interface AiAssistantConversationListResponse {
  tenant_code: string;
  results: AiAssistantConversationSummary[];
}

export interface AiAssistantConversationDetailResponse {
  tenant_code: string;
  conversation: AiAssistantConversationDetail;
}

export interface AiAssistantDashboardSuggestion {
  id: number;
  scope: string;
  title: string;
  body: string;
  severity: string;
  priority: string;
  related_entity_type: string;
  related_entity_id: string;
  created_at: string;
  expires_at: string | null;
  seen_at: string | null;
}

export interface AiAssistantDashboardSuggestionsResponse {
  tenant_code: string;
  cache: {
    hours: number;
    cached: boolean;
    generated: boolean;
    stale: boolean;
  };
  results: AiAssistantDashboardSuggestion[];
}
