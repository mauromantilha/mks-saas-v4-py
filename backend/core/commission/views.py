from rest_framework import generics
from commission.models import ParticipantProfile
from commission.serializers import ParticipantProfileSerializer
from operational.views import TenantScopedAPIViewMixin


class ParticipantProfileListCreateAPIView(TenantScopedAPIViewMixin, generics.ListCreateAPIView):
    model = ParticipantProfile
    serializer_class = ParticipantProfileSerializer
    tenant_resource_key = "participant_profiles"


class ParticipantProfileDetailAPIView(TenantScopedAPIViewMixin, generics.RetrieveUpdateDestroyAPIView):
    model = ParticipantProfile
    serializer_class = ParticipantProfileSerializer
    tenant_resource_key = "participant_profiles"