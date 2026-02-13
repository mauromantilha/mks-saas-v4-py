from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from operational.ai_assistant_api_service import AiAssistantApiService
from operational.ai_dashboard_suggestions_service import DashboardSuggestionsService
from operational.serializers import (
    AiConversationDetailSerializer,
    AiConversationMessageRequestSerializer,
    AiConversationSerializer,
    AiDashboardSuggestionSerializer,
    TenantAIAssistantRequestSerializer,
)
from tenancy.permissions import IsTenantRoleAllowed


class TenantAIAssistantConsultAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ai_assistant"

    def get(self, request):
        service = AiAssistantApiService.build()
        conversations = service.list_conversations(company=request.company, limit=30)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "results": AiConversationSerializer(conversations, many=True).data,
            }
        )

    def post(self, request):
        serializer = TenantAIAssistantRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = AiAssistantApiService.build()
        payload = service.consult(
            company=request.company,
            user=request.user,
            prompt=data["prompt"],
            conversation_id=data.get("conversation_id"),
            request=request,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class AiAssistantConversationListAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ai_assistant"

    def get(self, request):
        limit_raw = request.query_params.get("limit", "50")
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 50

        service = AiAssistantApiService.build()
        conversations = service.list_conversations(company=request.company, limit=limit)
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "results": AiConversationSerializer(conversations, many=True).data,
            }
        )


class AiAssistantConversationDetailAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ai_assistant"

    def get(self, request, conversation_id: int):
        service = AiAssistantApiService.build()
        conversation = service.get_conversation(
            company=request.company,
            conversation_id=conversation_id,
        )
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "conversation": AiConversationDetailSerializer(conversation).data,
            }
        )


class AiAssistantConversationMessageAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ai_assistant"

    def post(self, request, conversation_id: int):
        serializer = AiConversationMessageRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        prompt = serializer.validated_data["prompt"]

        service = AiAssistantApiService.build()
        # Validates tenant ownership before writing a new message.
        service.get_conversation(company=request.company, conversation_id=conversation_id)
        payload = service.consult(
            company=request.company,
            user=request.user,
            prompt=prompt,
            conversation_id=conversation_id,
            request=request,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class AiAssistantDashboardSuggestionsAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ai_assistant"

    def get(self, request):
        cache_hours = int(getattr(settings, "AI_DASHBOARD_SUGGESTIONS_CACHE_HOURS", 6) or 6)
        service = DashboardSuggestionsService.build(
            company=request.company,
            user=request.user,
            cache_hours=cache_hours,
        )
        suggestions, meta = service.list_or_generate()
        return Response(
            {
                "tenant_code": request.company.tenant_code,
                "cache": {
                    "hours": cache_hours,
                    **meta,
                },
                "results": AiDashboardSuggestionSerializer(suggestions, many=True).data,
            }
        )

