from rest_framework import serializers

from ledger.models import LedgerEntry


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = (
            "id",
            "scope",
            "company_id",
            "actor_username",
            "actor_email",
            "action",
            "event_type",
            "resource_label",
            "resource_pk",
            "occurred_at",
            "request_id",
            "request_method",
            "request_path",
            "ip_address",
            "user_agent",
            "chain_id",
            "prev_hash",
            "entry_hash",
            "data_before",
            "data_after",
            "metadata",
        )

