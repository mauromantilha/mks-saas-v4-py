from rest_framework import serializers
from insurance_core.models import PolicyDocument

class PolicyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDocument
        fields = (
            "id",
            "policy",
            "endorsement",
            "claim",
            "document_type",
            "file_name",
            "storage_key",
            "content_type",
            "file_size",
            "uploaded_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "storage_key",
            "uploaded_at",
            "created_at",
        )

class DocumentUploadRequestSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField()
    document_type = serializers.CharField(required=False, max_length=50)

class GenericDocumentUploadRequestSerializer(DocumentUploadRequestSerializer):
    entity_type = serializers.ChoiceField(choices=["POLICY", "ENDORSEMENT", "CLAIM"])
    entity_id = serializers.IntegerField()