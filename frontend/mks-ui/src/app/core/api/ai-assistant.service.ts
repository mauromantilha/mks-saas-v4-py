import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";

import { environment } from "../../../environments/environment";
import {
  AiAssistantConsultResponse,
  AiAssistantConversationDetailResponse,
  AiAssistantConversationListResponse,
  AiAssistantDashboardSuggestionsResponse,
} from "./ai-assistant.types";

@Injectable({ providedIn: "root" })
export class AiAssistantService {
  private readonly apiBase = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api`
    : "/api";

  constructor(private readonly http: HttpClient) {}

  consult(
    prompt: string,
    conversationId?: number
  ): Observable<AiAssistantConsultResponse> {
    const text = (prompt || "").trim();
    if (conversationId && conversationId > 0) {
      return this.http.post<AiAssistantConsultResponse>(
        `${this.apiBase}/ai-assistant/conversations/${conversationId}/message/`,
        { prompt: text }
      );
    }

    return this.http.post<AiAssistantConsultResponse>(
      `${this.apiBase}/ai-assistant/consult/`,
      { prompt: text }
    );
  }

  listConversations(limit = 50): Observable<AiAssistantConversationListResponse> {
    const params = new HttpParams().set("limit", String(Math.max(1, Math.min(100, limit))));
    return this.http.get<AiAssistantConversationListResponse>(
      `${this.apiBase}/ai-assistant/conversations/`,
      { params }
    );
  }

  getConversation(id: number): Observable<AiAssistantConversationDetailResponse> {
    return this.http.get<AiAssistantConversationDetailResponse>(
      `${this.apiBase}/ai-assistant/conversations/${id}/`
    );
  }

  dashboardSuggestions(): Observable<AiAssistantDashboardSuggestionsResponse> {
    return this.http.get<AiAssistantDashboardSuggestionsResponse>(
      `${this.apiBase}/ai-assistant/dashboard-suggestions/`
    );
  }
}
