from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from ledger.models import LedgerEntry
from ledger.serializers import LedgerEntrySerializer
from tenancy.permissions import IsTenantRoleAllowed


class TenantLedgerEntryListAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "ledger"

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "200"))
        except ValueError:
            limit = 200
        limit = max(1, min(limit, 1000))

        entries = (
            LedgerEntry.all_objects.filter(
                scope=LedgerEntry.SCOPE_TENANT,
                company=request.company,
            )
            .order_by("-occurred_at", "-id")[:limit]
        )
        return Response(LedgerEntrySerializer(entries, many=True).data)


class PlatformLedgerEntryListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "200"))
        except ValueError:
            limit = 200
        limit = max(1, min(limit, 1000))

        entries = (
            LedgerEntry.all_objects.filter(scope=LedgerEntry.SCOPE_PLATFORM)
            .order_by("-occurred_at", "-id")[:limit]
        )
        return Response(LedgerEntrySerializer(entries, many=True).data)

