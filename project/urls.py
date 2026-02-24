from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include
from .views import LandingPageView, PrivacyPolicyView, TermsOfServiceView

urlpatterns = [
    path("", LandingPageView.as_view(), name="landing_page"),
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy_policy"),
    path("terms-of-service/", TermsOfServiceView.as_view(), name="terms_of_service"),
    # Authentication URLs
    path("auth/", include("users_app.urls")),
    # Main application URLs
    path("record/", include("brain_dump_app.urls")),
    # Mobile API endpoints
    path("api/", include("brain_dump_app.api_urls")),
    # Subscription URLs
    path("subscriptions/", include("subscriptions_app.urls")),
    # WhatsApp webhook
    path("whatsapp/", include("whatsapp_app.urls")),
]

admin.site.site_title = "Brain Dump"
admin.site.site_header = "Brain Dump"
admin.site.index_title = "Welcome to Brain Dump"

# Define error handlers
handler403 = "project.views.handler403"
handler404 = "project.views.handler404"
handler500 = "project.views.handler500"

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("admin/", admin.site.urls),
        path("__debug__/", include(debug_toolbar.urls)),
    ]
