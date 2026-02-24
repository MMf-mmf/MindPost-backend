from django.shortcuts import render, redirect


def handler403(request, exception=None):
    return render(request, "base/403.html", status=403)


def handler404(request, exception=None):
    return render(request, "base/404.html", status=404)


def handler500(request):
    return render(request, "base/500.html", status=500)


def custom_error_view(request, exception=None, error_title=None, error_message=None):
    context = {
        "error_title": error_title,
        "error_message": error_message,
    }
    return render(request, "admin/error.html", context)


from django.views.generic import TemplateView

# Create your views here.


def health_check(request):
    return render(request, "base/health_check.html")


class LandingPageView(TemplateView):
    template_name = "base/landing_page.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(
                "brain_dump"
            )  # Corrected to the actual name of the root URL in brain_dump_app
        return super().get(request, *args, **kwargs)


class PrivacyPolicyView(TemplateView):
    template_name = "base/privacy_policy.html"


class TermsOfServiceView(TemplateView):
    template_name = "base/terms_of_service.html"
