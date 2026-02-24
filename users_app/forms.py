from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """
    A form for creating new users with email instead of username
    """

    email = forms.EmailField(
        max_length=255,
        required=True,
        help_text="Required. Enter a valid email address.",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    email2 = forms.EmailField(
        label="Confirm Email",
        max_length=255,
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "email2",
            # "subscription_tier", # Removed
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        email2 = cleaned_data.get("email2")

        if email and email2 and email != email2:
            self.add_error("email2", "Emails do not match.")

        # Ensure subscription_tier is either free or pro - REMOVED
        # tier = cleaned_data.get("subscription_tier")
        # if tier not in ["basic", "pro"]:
        #     self.add_error(
        #         "subscription_tier", "Please select a valid subscription plan."
        #     )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # Set username to email

        # Let the view handle the tier and final save
        if commit:
            user.save()
        return user
