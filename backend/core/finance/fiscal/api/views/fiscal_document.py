from __future__ import annotations

from django.db import models
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from finance.fiscal.api.serializers.fiscal_document import (
    FiscalDocumentSerializer,
    IssueFiscalSerializer,
)
from finance.fiscal.models import FiscalDocument
from finance.fiscal.services import (
    FiscalCancelAlreadyCancelled,
    FiscalCancelError,
    FiscalIssueError,
    issue_nf_from_invoice,
    cancel_nf,
)
from tenancy.permissions import IsTenantRoleAllowed


class FiscalDocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FiscalDocumentSerializer
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "fiscal_documents"

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return FiscalDocument.objects.none()

        qs = (
            FiscalDocument.all_objects.filter(company=company)
            .select_related("customer_snapshot")
            .order_by("-issue_date", "-id")
        )

        status_filter = (self.request.query_params.get("status") or "").strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)

        invoice_id = (self.request.query_params.get("invoice_id") or "").strip()
        if invoice_id:
            try:
                qs = qs.filter(invoice_id=int(invoice_id))
            except ValueError:
                return FiscalDocument.objects.none()

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            qs = qs.filter(
                models.Q(number__icontains=search)
                | models.Q(series__icontains=search)
                | models.Q(provider_document_id__icontains=search)
            )

        return qs

    @action(detail=False, methods=["post"], url_path="issue")
    def issue(self, request):
        serializer = IssueFiscalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            doc = issue_nf_from_invoice(
                serializer.validated_data["invoice_id"],
                actor=request.user,
                request=request,
            )
        except FiscalIssueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            return Response(
                {"detail": "Failed to issue fiscal document."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self.get_serializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        doc = self.get_object()
        target_document_id = (doc.provider_document_id or "").strip() or str(doc.id)

        try:
            cancelled = cancel_nf(target_document_id, actor=request.user, request=request)
        except FiscalCancelAlreadyCancelled as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except FiscalCancelError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:  # pragma: no cover
            return Response(
                {"detail": "Failed to cancel fiscal document."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self.get_serializer(cancelled).data, status=status.HTTP_200_OK)

