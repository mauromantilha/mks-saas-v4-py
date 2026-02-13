from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.shortcuts import get_object_or_404

from operational.ai_assistant_service import AiAssistantService
from operational.models import AiConversation


@dataclass
class AiAssistantApiService:
    ai_service: AiAssistantService

    @classmethod
    def build(cls) -> "AiAssistantApiService":
        return cls(ai_service=AiAssistantService())

    def consult(
        self,
        *,
        company,
        user,
        prompt: str,
        conversation_id: int | None = None,
        request=None,
    ) -> dict[str, Any]:
        result = self.ai_service.consult(
            company=company,
            user=user,
            prompt=prompt,
            context={"conversation_id": conversation_id},
            request=request,
        )
        sources = result.get("sources", {})
        assistant_payload = result.get("assistant", {})
        return {
            "conversation_id": result.get("conversation_id"),
            "answer": str(assistant_payload.get("summary") or ""),
            "sources": {
                "web": sources.get("web_sources", []),
                "internal": sources.get("internal_sources", []),
            },
            "metrics_used": sources.get("metrics_used", []),
            "suggestions": result.get("next_actions", []),
            "intents": result.get("intents", []),
            "correlation_id": result.get("correlation_id"),
        }

    @staticmethod
    def list_conversations(*, company, limit: int = 50):
        safe_limit = max(1, min(100, int(limit)))
        return (
            AiConversation.all_objects.filter(company=company)
            .select_related("created_by")
            .order_by("-updated_at", "-id")[:safe_limit]
        )

    @staticmethod
    def get_conversation(*, company, conversation_id: int):
        return get_object_or_404(
            AiConversation.all_objects.select_related("created_by").prefetch_related("messages"),
            company=company,
            id=conversation_id,
        )

