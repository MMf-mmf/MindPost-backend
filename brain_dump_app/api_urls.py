from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from .api import (
    BrainDumpViewSet,
    PostViewSet,
    TwitterConnectionViewSet,
    BrainDumpChatAPIView,
    AccountDeleteAPIView,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"brain-dumps", BrainDumpViewSet, basename="api-brain-dumps")
router.register(r"posts", PostViewSet, basename="api-posts")
router.register(r"twitter-connection", TwitterConnectionViewSet, basename="api-twitter")

# The API URLs are determined automatically by the router
urlpatterns = [
    # JWT Authentication endpoints
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Chat endpoint
    path(
        "brain-dumps/chat/", BrainDumpChatAPIView.as_view(), name="api-brain-dumps-chat"
    ),
    # Account deletion endpoint
    path("account/delete/", AccountDeleteAPIView.as_view(), name="api-account-delete"),
    # Include the router URLs
    path("", include(router.urls)),
]
