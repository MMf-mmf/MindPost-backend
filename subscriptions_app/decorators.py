# Decorators for subscription and usage checks
import functools
import logging
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from rest_framework.response import Response
from rest_framework import status as drf_status

# Import both utils
from .utils import check_usage, check_and_reset_daily_limits

logger = logging.getLogger("project")


def limit_check(limit_type: str, value_to_add: int = 1, skip_get: bool = True):
    """
    Decorator factory to check usage limits before executing a view.

    Handles both standard Django views and DRF API views.

    Args:
        limit_type: The key corresponding to the limit in settings (e.g., 'max_recording').
        value_to_add: The amount that the action intends to add to the usage count.
        skip_get: If True, skip limit checks for GET requests to avoid redirect loops.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # For class-based views (DRF), request is the second argument
            actual_request = request if hasattr(request, "user") else args[0]

            # Skip the check for GET requests if skip_get is True
            if skip_get and actual_request.method == "GET":
                return view_func(request, *args, **kwargs)

            if not actual_request.user.is_authenticated:
                # Should be handled by @login_required or DRF permissions,
                # but good to have a fallback.
                # Check if DRF request
                if hasattr(actual_request, "accepted_renderer"):
                    return Response(
                        {"detail": "Authentication credentials were not provided."},
                        status=drf_status.HTTP_401_UNAUTHORIZED,
                    )
                else:
                    # Redirect to login for standard views
                    return redirect(f"{reverse('login')}?next={actual_request.path}")

            # --- Check and Reset Daily Limits ---
            check_and_reset_daily_limits(actual_request.user)
            # --- End Check and Reset ---

            # Perform the usage check
            if not check_usage(actual_request.user, limit_type, value_to_add):
                # Determine if it's a DRF request
                is_drf_request = hasattr(actual_request, "accepted_renderer")

                error_message = f"Usage limit reached for '{limit_type}'. Please upgrade your plan for higher limits."

                if is_drf_request:
                    # Return DRF Response for API views
                    logger.warning(
                        f"DRF Limit Check Failed: User {actual_request.user.email}, Limit: {limit_type}"
                    )
                    return Response(
                        {"detail": error_message},
                        status=drf_status.HTTP_403_FORBIDDEN,
                    )
                else:
                    # Add Django message and redirect for standard views
                    logger.warning(
                        f"Django Limit Check Failed: User {actual_request.user.email}, Limit: {limit_type}"
                    )
                    messages.error(actual_request, error_message)
                    # Redirect to an upgrade page or maybe the referring page?
                    # Let's redirect to the subscription upgrade page for now.
                    # Make sure 'upgrade_page' is a valid URL name.
                    try:
                        upgrade_url = reverse("subscriptions_app:upgrade_page")
                        return redirect(upgrade_url)
                    except Exception:
                        logger.error(
                            "URL name 'upgrade_page' not found, redirecting to home."
                        )
                        # Fallback redirect if 'upgrade_page' doesn't exist
                        return redirect("/")  # Or maybe settings page?

            # If check passes, execute the original view
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
