from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.services import preview_endorsement_impact
from insurance_core.models import Policy, Endorsement, PolicyBillingConfig, Claim, PolicyDocument
from insurance_core.services.legacy import (
    create_endorsement, 
    issue_policy, 
    create_claim, 
    transition_claim_status, 
    create_document_upload_url,
    confirm_document_upload,
    get_document_download_url,
    renew_policy
)
from insurance_core.api.serializers.policy import (
    EndorsementSerializer,
    PolicySerializer,
    EndorsementCreateSerializer,
    PolicyCreateSerializer,
    PolicyRenewSerializer,
    EndorsementSimulationSerializer,
)
from insurance_core.api.serializers.claims import (
    ClaimSerializer,
    ClaimCreateSerializer,
    ClaimTransitionSerializer,
)
from insurance_core.api.serializers.documents import (
    DocumentUploadRequestSerializer,
    GenericDocumentUploadRequestSerializer,
    PolicyDocumentSerializer,
)
from insurance_core.api.serializers.finance import InstallmentPreviewSerializer
from tenancy.permissions import IsTenantRoleAllowed


class PolicyEndorsementListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = EndorsementSerializer
    tenant_resource_key = "endossos"

    def get_queryset(self):
        policy_id = self.kwargs["policy_id"]
        return Endorsement.objects.filter(
            policy__id=policy_id,
            company=self.request.company
        ).order_by("-issue_date", "-created_at")

    def create(self, request, *args, **kwargs):
        policy_id = self.kwargs["policy_id"]
        policy = get_object_or_404(Policy, id=policy_id, company=request.company)
        
        serializer = EndorsementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endorsement = create_endorsement(
            policy=policy,
            endorsement_type=serializer.validated_data["endorsement_type"],
            effective_date=serializer.validated_data["effective_date"],
            premium_delta=serializer.validated_data.get("premium_delta") or Decimal("0.00"),
            description=serializer.validated_data.get("description", ""),
            user=request.user
        )
        
        return Response(
            EndorsementSerializer(endorsement).data,
            status=status.HTTP_201_CREATED
        )


class PolicyListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def get_queryset(self):
        return Policy.objects.filter(company=self.request.company).select_related(
            "customer", "insurer", "product", "branch", "billing_config"
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PolicyCreateSerializer
        return PolicySerializer

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)


class PolicyDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = PolicySerializer
    tenant_resource_key = "policies"
    
    def get_queryset(self):
        return Policy.objects.filter(company=self.request.company).select_related(
            "customer", "insurer", "product", "branch", "billing_config"
        )


class PolicyIssueAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def post(self, request, pk):
        policy = get_object_or_404(Policy, pk=pk, company=request.company)
        issue_policy(policy, request.user)
        return Response(PolicySerializer(policy).data)


class PolicyCancelAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def post(self, request, pk):
        policy = get_object_or_404(Policy, pk=pk, company=request.company)
        effective_date_str = request.data.get("effective_date")
        if not effective_date_str:
            return Response({"detail": "effective_date is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        create_endorsement(policy, Endorsement.TYPE_CANCEL, effective_date_str, user=request.user)
        return Response(PolicySerializer(policy).data)


class PolicyRenewAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def post(self, request, pk):
        policy = get_object_or_404(Policy, pk=pk, company=request.company)
        serializer = PolicyRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_policy = renew_policy(
            policy=policy,
            user=request.user,
            **serializer.validated_data
        )
        return Response(PolicySerializer(new_policy).data, status=status.HTTP_201_CREATED)


class EndorsementSimulationAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "endossos"

    def post(self, request, policy_id):
        policy = get_object_or_404(Policy, id=policy_id, company=request.company)
        serializer = EndorsementSimulationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        preview = preview_endorsement_impact(
            company=request.company,
            policy_id=policy.id,
            endorsement_type=data["endorsement_type"],
            premium_delta=data.get("premium_delta") or Decimal("0.00"),
            effective_date=data["effective_date"]
        )

        return Response(InstallmentPreviewSerializer(preview, many=True).data)


class ClaimListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = ClaimSerializer
    tenant_resource_key = "claims" # Needs to be added to RBAC

    def get_queryset(self):
        qs = Claim.objects.filter(company=self.request.company).select_related("policy")
        policy_id = self.kwargs.get("policy_id")
        if policy_id:
            qs = qs.filter(policy_id=policy_id)
        return qs.order_by("-report_date")

    def create(self, request, *args, **kwargs):
        policy_id = self.kwargs.get("policy_id")
        if not policy_id:
            return Response({"detail": "Policy ID required in URL."}, status=status.HTTP_400_BAD_REQUEST)
        
        policy = get_object_or_404(Policy, id=policy_id, company=request.company)
        serializer = ClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        claim = create_claim(
            policy=policy,
            user=request.user,
            **serializer.validated_data
        )
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


class ClaimDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = ClaimSerializer
    tenant_resource_key = "claims"

    def get_queryset(self):
        return Claim.objects.filter(company=self.request.company).select_related("policy")


class ClaimTransitionAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "claims"

    def post(self, request, pk):
        claim = get_object_or_404(Claim, pk=pk, company=request.company)
        serializer = ClaimTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transition_claim_status(claim, user=request.user, **serializer.validated_data)
        
        return Response(ClaimSerializer(claim).data)


class BaseDocumentUploadAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    model = None
    tenant_resource_key = None

    def post(self, request, pk):
        entity = get_object_or_404(self.model, pk=pk, company=request.company)
        serializer = DocumentUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc, upload_url = create_document_upload_url(
            company=request.company,
            entity=entity,
            user=request.user,
            **serializer.validated_data
        )
        
        # If document_type was passed, update it
        if serializer.validated_data.get("document_type"):
            doc.document_type = serializer.validated_data["document_type"]
            doc.save(update_fields=["document_type"])

        return Response({
            "document_id": doc.id,
            "upload_url": upload_url,
            "storage_key": doc.storage_key,
            "expiration_minutes": 15
        }, status=status.HTTP_201_CREATED)


class PolicyDocumentUploadAPIView(BaseDocumentUploadAPIView):
    model = Policy
    tenant_resource_key = "policies"


class EndorsementDocumentUploadAPIView(BaseDocumentUploadAPIView):
    model = Endorsement
    tenant_resource_key = "endossos"


class ClaimDocumentUploadAPIView(BaseDocumentUploadAPIView):
    model = Claim
    tenant_resource_key = "claims"


class GenericDocumentUploadAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    # Resource key is dynamic or we use a general one. Using 'policies' as fallback/base.
    tenant_resource_key = "policies"

    def post(self, request):
        serializer = GenericDocumentUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entity_type = serializer.validated_data["entity_type"]
        entity_id = serializer.validated_data["entity_id"]
        
        model_map = {
            "POLICY": Policy,
            "ENDORSEMENT": Endorsement,
            "CLAIM": Claim,
        }
        model = model_map[entity_type]
        
        entity = get_object_or_404(model, pk=entity_id, company=request.company)

        doc, upload_url = create_document_upload_url(
            company=request.company,
            entity=entity,
            user=request.user,
            **{k: v for k, v in serializer.validated_data.items() if k not in ("entity_type", "entity_id")}
        )

        return Response({
            "document_id": doc.id,
            "upload_url": upload_url,
            "storage_key": doc.storage_key,
            "expiration_minutes": 15
        }, status=status.HTTP_201_CREATED)


class DocumentConfirmUploadAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    # This endpoint is generic, permissions are checked via the document's policy ownership
    
    def post(self, request, pk):
        document = get_object_or_404(PolicyDocument, pk=pk, company=request.company, deleted_at__isnull=True)
        confirm_document_upload(document)
        return Response(PolicyDocumentSerializer(document).data)


class DocumentDownloadAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]

    def get(self, request, pk):
        document = get_object_or_404(PolicyDocument, pk=pk, company=request.company, deleted_at__isnull=True)
        url = get_document_download_url(document)
        if not url:
            return Response({"detail": "Could not generate download URL."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"download_url": url})


class DocumentDetailAPIView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = PolicyDocumentSerializer
    tenant_resource_key = "policies"

    def get_queryset(self):
        return PolicyDocument.objects.filter(
            company=self.request.company,
            deleted_at__isnull=True
        )

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])


class PolicyDocumentListAPIView(generics.ListAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = PolicyDocumentSerializer
    tenant_resource_key = "policies"

    def get_queryset(self):
        policy_id = self.kwargs["policy_id"]
        # Ensure policy exists and belongs to tenant
        get_object_or_404(Policy, id=policy_id, company=self.request.company)
        
        queryset = PolicyDocument.objects.filter(
            policy_id=policy_id,
            company=self.request.company,
            deleted_at__isnull=True
        ).select_related("endorsement", "claim").order_by("-created_at")

        document_type = self.request.query_params.get("document_type")
        if document_type:
            queryset = queryset.filter(document_type=document_type)

        return queryset


class DocumentTrashListAPIView(generics.ListAPIView):
    permission_classes = [IsTenantRoleAllowed]
    serializer_class = PolicyDocumentSerializer
    tenant_resource_key = "policies"

    def get_queryset(self):
        return PolicyDocument.objects.filter(
            company=self.request.company,
            deleted_at__isnull=False
        ).select_related("endorsement", "claim").order_by("-deleted_at")


class DocumentRestoreAPIView(APIView):
    permission_classes = [IsTenantRoleAllowed]
    tenant_resource_key = "policies"

    def post(self, request, pk):
        document = get_object_or_404(
            PolicyDocument,
            pk=pk,
            company=request.company,
            deleted_at__isnull=False
        )
        document.deleted_at = None
        document.save(update_fields=["deleted_at", "updated_at"])
        return Response(PolicyDocumentSerializer(document).data)
