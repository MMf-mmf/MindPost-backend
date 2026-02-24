# Utility functions for subscription and usage checks
import logging
from datetime import date  # Import date
from django.conf import settings
from users_app.models import CustomUser  # Assuming CustomUser is in users_app

logger = logging.getLogger("project")


def check_and_reset_daily_limits(user: CustomUser):
    """Checks if usage limits need resetting for the day and resets them."""
    if not user or not hasattr(user, "rate_limit_last_reset"):
        # Avoid errors if user object is weird or migration hasn't run
        logger.warning(
            f"Skipping daily limit reset check for invalid user object: {user}"
        )
        return

    today = date.today()
    # Check if the last reset date is not today (or if it's None)
    if user.rate_limit_last_reset != today:
        logger.info(
            f"Resetting daily usage limits for user {user.email} (ID: {user.id}) for date {today}. Previous reset date: {user.rate_limit_last_reset}"
        )
        # Define fields to reset
        fields_to_reset = {
            "current_recordings": 0,
            "current_post_generations": 0,
            "current_post_submissions": 0,
            "current_chat_messages": 0,
        }
        fields_to_update = list(fields_to_reset.keys()) + ["rate_limit_last_reset"]

        # Apply resets
        for field, value in fields_to_reset.items():
            setattr(user, field, value)
        user.rate_limit_last_reset = today

        try:
            user.save(update_fields=fields_to_update)
        except Exception as e:
            logger.error(
                f"Failed to save user {user.email} after resetting daily limits: {e}",
                exc_info=True,
            )
            # Log error, but continue. The state in memory is reset, but DB might be stale.


def get_user_limits(user: CustomUser) -> dict | None:
    """
    Fetches the limits dictionary based on the user's subscription tier and status.

    Args:
        user: The CustomUser instance.

    Returns:
        A dictionary containing the limits (e.g., settings.BASIC_USER)
        or None if the user has no active subscription or tier.
    """
    if (
        not user
        or not user.subscription_tier
        or user.subscription_status not in ["active", "trialing"]
    ):
        return None

    tier = user.subscription_tier.upper()
    if tier == "BASIC":
        return settings.BASIC_USER
    elif tier == "PRO":
        return settings.PRO_USER
    else:
        logger.warning(
            f"Unknown subscription tier '{user.subscription_tier}' for user {user.email}"
        )
        return None


def check_usage(user: CustomUser, limit_type: str, value_to_add: int = 1) -> bool:
    """
    Checks if a user can perform an action based on their usage limits.

    Args:
        user: The CustomUser instance.
        limit_type: The key corresponding to the limit in settings (e.g., 'max_recording').
        value_to_add: The amount to add to the current usage count for checking.

    Returns:
        True if the action is allowed, False otherwise.
    """
    limits = get_user_limits(user)
    if not limits:
        logger.info(
            f"Usage check failed for user {user.email}: No active subscription or limits found."
        )
        return False  # No active subscription or limits defined

    # Map limit_type (from settings) to the corresponding field name on CustomUser
    usage_field_map = {
        "max_recording": "current_recordings",
        "max_post_generations": "current_post_generations",
        "max_post_submissions": "current_post_submissions",
        "max_chat_messages": "current_chat_messages",
        # Note: max_recording_length is handled separately by check_recording_length
    }

    usage_field = usage_field_map.get(limit_type)
    if not usage_field:
        logger.error(f"Invalid limit_type '{limit_type}' passed to check_usage.")
        return False  # Should not happen if called correctly

    current_usage = getattr(user, usage_field, 0)
    limit = limits.get(limit_type)

    if limit is None:
        logger.warning(
            f"Limit type '{limit_type}' not found in settings for tier {user.subscription_tier}."
        )
        return True  # If limit isn't defined, allow the action? Or should it be False? Let's allow for now.

    if current_usage + value_to_add > limit:
        logger.info(
            f"Usage limit exceeded for user {user.email}: {limit_type} (Limit: {limit}, Current: {current_usage}, Adding: {value_to_add})"
        )
        return False  # Limit exceeded
    else:
        return True


def check_recording_length(user: CustomUser, duration_minutes: float) -> bool:
    """
    Checks if the duration of a recording is within the user's limit.

    Args:
        user: The CustomUser instance.
        duration_minutes: The duration of the recording in minutes.

    Returns:
        True if the duration is allowed, False otherwise.
    """
    limits = get_user_limits(user)
    if not limits:
        logger.info(
            f"Recording length check failed for user {user.email}: No active subscription or limits found."
        )
        return False  # No active subscription

    max_length = limits.get("max_recording_length")
    if max_length is None:
        logger.warning(
            f"max_recording_length not found in settings for tier {user.subscription_tier}."
        )
        return True  # Allow if not defined?

    if duration_minutes > max_length:
        logger.info(
            f"Recording length limit exceeded for user {user.email}: (Limit: {max_length} min, Attempted: {duration_minutes} min)"
        )
        return False
    else:
        return True
