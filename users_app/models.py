from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
import uuid


class CustomUserManger(UserManager):
    pass


class CustomUser(AbstractUser):
    """
    ******django default user model has the following fields******
    email,
    username,
    password,
    first_name,
    last_name,
    is_superuser,
    is_staff,
    is_active,
    date_joined
    last_login,
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CustomUserManger()

    # override username field to be non unique and null true
    username = models.CharField(max_length=30, unique=False, null=True)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        help_text="User's phone number for WhatsApp integration.",
    )

    # Subscription fields
    SUBSCRIPTION_TIER_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
    ]
    SUBSCRIPTION_STATUS_CHOICES = [
        ("active", "Active"),
        ("canceled", "Canceled"),
        ("incomplete", "Incomplete"),
        ("past_due", "Past Due"),
        ("pending_payment", "Pending Payment"),
        ("trialing", "Trialing"),  # free trial period
        # Add other relevant Stripe subscription statuses
    ]
    subscription_tier = models.CharField(
        max_length=10,
        choices=SUBSCRIPTION_TIER_CHOICES,
        null=True,  # Allow null initially
        blank=True,
        help_text="User's current subscription tier.",
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Status of the user's Stripe subscription.",
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe Customer ID for billing.",
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Stripe Subscription ID.",
    )

    # Usage tracking fields
    current_recordings = models.PositiveIntegerField(
        default=0, help_text="Number of recordings made in the current period."
    )
    current_post_generations = models.PositiveIntegerField(
        default=0,
        help_text="Number of posts generated in the current period.",  # USED FOR MATRIX
    )
    current_post_submissions = models.PositiveIntegerField(
        default=0,
        help_text="Number of posts submitted/published in the current period.",
    )
    current_chat_messages = models.PositiveIntegerField(
        default=0, help_text="Number of chat messages sent in the current period."
    )
    rate_limit_last_reset = models.DateField(
        null=True, blank=True, help_text="Date when usage counters were last reset."
    )

    # create a get_full_name method
    def get_full_name(self):
        return self.first_name + " " + self.last_name

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
