from django.urls import path
from commission.views import (
    ParticipantProfileListCreateAPIView,
    ParticipantProfileDetailAPIView,
)

urlpatterns = [
    path(
        "profiles/",
        ParticipantProfileListCreateAPIView.as_view(),
        name="participant-profiles-list",
    ),
    path(
        "profiles/<int:pk>/",
        ParticipantProfileDetailAPIView.as_view(),
        name="participant-profiles-detail",
    ),
]