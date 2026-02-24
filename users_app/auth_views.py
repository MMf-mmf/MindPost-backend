from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib import messages
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from django.conf import settings
from .forms import CustomUserCreationForm

# No longer importing create_trial_subscription here
# from subscriptions_app.views import create_trial_subscription


def login_view(request):
    """
    Handle user login with standard Django authentication.
    """
    if request.user.is_authenticated:
        return redirect("brain_dump_list")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            remember_me = request.POST.get("remember_me", False) == "on"

            user = authenticate(username=username, password=password)
            if user is not None:
                # Proceed with normal login (pending payment check removed)
                login(request, user)

                # Set session expiry based on remember_me checkbox
                if not remember_me:
                    # Session expires when browser closes
                    request.session.set_expiry(0)

                # Redirect to the next page if provided, otherwise to the brain dump list
                next_url = request.GET.get("next", "brain_dump_list")
                return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = AuthenticationForm()

    return render(request, "auth/login.html", {"form": form})


def signup_view(request):
    """
    Handle new user registration.
    """
    if request.user.is_authenticated:
        return redirect("brain_dump_list")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            # Save user instance without committing to DB yet
            # Save user instance, setting the chosen tier but no status yet
            user = form.save(commit=False)
            # selected_tier = form.cleaned_data.get("subscription_tier") # Removed
            # user.subscription_tier = selected_tier # Removed
            # Leave subscription_status, stripe_customer_id, stripe_subscription_id as null
            user.save()

            # Log the user in
            login(request, user)

            # Redirect user to the upgrade/checkout page to provide payment details and start trial
            # tier_display = ( # Removed
            #     selected_tier.capitalize() if selected_tier else "selected"
            # )  # Defensive capitalization
            messages.info(
                request,
                # f"Account created! Please complete the checkout for your {tier_display} plan to start your free trial.",
                "Account created! Please choose a plan on the next page to start your free trial.",
            )
            return redirect("subscriptions_app:upgrade_page")
    else:
        form = CustomUserCreationForm()  # Removed initial value for subscription_tier

    return render(request, "auth/signup.html", {"form": form})


def logout_view(request):
    """
    Handle user logout.
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("login")


class CustomPasswordResetView(PasswordResetView):
    """
    Custom password reset view to use our templates.
    """

    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.html"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """
    Custom password reset done view to use our templates.
    """

    template_name = "auth/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Custom password reset confirmation view to use our templates.
    """

    template_name = "auth/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """
    Custom password reset complete view to use our templates.
    """

    template_name = "auth/password_reset_complete.html"
