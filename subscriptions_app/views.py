import json  # Import json for parsing request body
import stripe
from stripe import Subscription as StripeSubscription
from datetime import timedelta  # Keep timedelta import
from django.utils import (
    timezone,
)  # Import Django's timezone utilities instead of datetime

# from stripe.error import SignatureVerificationError # Reverted import
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login  # Import login
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse  # Import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages

from users_app.models import CustomUser
from django.conf import settings  # Import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


# Helper function to create trial subscription
def create_trial_subscription(user: CustomUser, price_id: str):
    """Creates a Stripe customer and a trial subscription."""
    try:
        # 1. Create Stripe Customer if one doesn't exist
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                metadata={"django_user_id": str(user.id)},
            )
            user.stripe_customer_id = customer.id
            # Save immediately to prevent race conditions if subscription fails
            user.save(update_fields=["stripe_customer_id"])
        # No else needed, customer_id is already on the user object if it exists

        # 2. Create Stripe Subscription with Trial
        subscription = stripe.Subscription.create(
            customer=user.stripe_customer_id,  # Use the potentially updated ID
            items=[{"price": price_id}],
            trial_period_days=14,  # Or get from settings
            # Optional: Add metadata to subscription if needed
            metadata={"django_user_id": str(user.id)},
            # Expand the latest invoice and payment intent for immediate status check if needed
            # expand=["latest_invoice.payment_intent"],
        )
        user.stripe_subscription_id = subscription.id
        user.subscription_status = subscription.status  # Should be 'trialing'

        # Determine tier based on price_id
        if price_id == settings.STRIPE_BASIC_PRICE_ID:
            user.subscription_tier = "basic"
        elif price_id == settings.STRIPE_PRO_PRICE_ID:
            user.subscription_tier = "pro"
        else:
            # Handle error: unknown price ID
            print(
                f"Error: Unknown price_id '{price_id}' during trial creation for {user.email}"
            )
            # Potentially raise an exception or return an error status
            # Clean up? Maybe delete the Stripe customer?
            return False  # Indicate failure

        # Save updated user fields (tier, status, subscription_id)
        user.save(
            update_fields=[
                "stripe_subscription_id",
                "subscription_status",
                "subscription_tier",
            ]
        )
        print(
            f"Trial subscription '{user.subscription_tier}' created for {user.email}. Status: {user.subscription_status}"
        )
        return True  # Indicate success

    except stripe.StripeError as e:
        print(f"Stripe Error creating trial for {user.email}: {e}")
        # Clean up? Maybe delete the Stripe customer if the subscription failed?
        # Or log the error and handle manually.
        return False  # Indicate failure
    except Exception as e:
        print(f"Unexpected Error creating trial for {user.email}: {e}")
        return False  # Indicate failure


# View for handling the upgrade process for *already logged-in* users
@login_required
def upgrade_page_view(request):
    user = request.user
    subscription_canceling = False  # Default value

    # Check if the user has a subscription ID
    if user.stripe_subscription_id:
        try:
            # Retrieve the subscription from Stripe
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
            # Check if it's set to cancel at period end
            if subscription.cancel_at_period_end:
                subscription_canceling = True
        except stripe.StripeError as e:
            # Handle potential errors (e.g., subscription not found)
            print(
                f"Error retrieving subscription {user.stripe_subscription_id} for user {user.email}: {e}"
            )
            messages.error(
                request,
                "Could not retrieve your current subscription details. Please contact support.",
            )
            # Decide how to proceed - maybe redirect or show an error state?
            # For now, we'll proceed with subscription_canceling = False

    # Pass Stripe public key, price IDs, and cancellation status to the template
    context = {
        "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
        "basic_price_id": settings.STRIPE_BASIC_PRICE_ID,
        "pro_price_id": settings.STRIPE_PRO_PRICE_ID,
        "subscription_canceling": subscription_canceling,  # Add the canceling status
    }
    return render(request, "subscriptions_app/upgrade.html", context)


# This view handles POST requests from the upgrade page (logged-in users).
@login_required
@require_POST  # Ensure POST requests
def create_checkout_session_view(request):
    """
    Creates a Stripe Checkout session for logged-in users upgrading or reactivating.
    Accepts a price_id via JSON body.
    """
    try:
        data = json.loads(request.body)
        price_id = data.get("priceId")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if not price_id:
        return JsonResponse({"error": "priceId is required."}, status=400)

    # Validate price_id against known ones (optional but recommended)
    if price_id not in [settings.STRIPE_BASIC_PRICE_ID, settings.STRIPE_PRO_PRICE_ID]:
        return JsonResponse({"error": "Invalid priceId."}, status=400)

    user = request.user
    print(f"Creating session for user {user.email} with price {price_id}")

    # Construct absolute URLs
    protocol = request.scheme  # Fix indentation
    host = request.get_host()  # Fix indentation
    # Build URLs relative to the current request
    success_url_path = reverse(
        "subscriptions_app:payment_success"
    )  # Use reverse for safety
    cancel_url_path = reverse(  # Fix indentation
        "subscriptions_app:payment_cancel"
    )  # Use reverse for safety
    success_url = (  # Fix indentation
        f"{protocol}://{host}{success_url_path}?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{protocol}://{host}{cancel_url_path}"

    try:
        # Check if user already has a Stripe customer ID, create if not
        customer_id = user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                # Add any other relevant customer details or metadata
                metadata={"django_user_id": str(user.id)},
            )
            customer_id = customer.id
            # Save the new customer ID to the user model
            user.stripe_customer_id = customer_id
            # Use update_fields for efficiency if user object already exists
            user.save(update_fields=["stripe_customer_id"])

        # Check if the user is eligible for a trial
        # Eligible if: account < 90 days old, never had a subscription, no Stripe IDs
        ninety_days_ago = timezone.now() - timedelta(
            days=90
        )  # Use timezone.now() instead of datetime.now()
        is_eligible_for_trial = (
            user.date_joined > ninety_days_ago
            and user.subscription_status is None
            and not user.stripe_subscription_id
        )

        # Create checkout session parameters
        checkout_params = {
            "ui_mode": "embedded",
            "customer": customer_id,
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            "mode": "subscription",
            "return_url": success_url,
            "metadata": {"django_user_id": str(user.id)},
        }

        # Only add trial period if user is eligible
        if is_eligible_for_trial:
            checkout_params["subscription_data"] = {"trial_period_days": 14}
            print(f"User {user.email} is eligible for free trial")
        else:
            print(f"User {user.email} is NOT eligible for free trial")

        # Create the Stripe Checkout session using the provided price_id
        checkout_session = stripe.checkout.Session.create(**checkout_params)

        # Return the client secret needed by Stripe.js
        return JsonResponse({"clientSecret": checkout_session.client_secret})

    # Reorder except blocks: Specific first, then general
    except stripe.StripeError as e:  # Catch Stripe specific errors first
        print(f"Stripe Error creating checkout session: {e}")
        return JsonResponse(
            {"error": f"Stripe error: {str(e)}"}, status=500
        )  # Use str(e) for message
    except Exception as e:  # Catch general exceptions last
        print(f"Error creating Stripe session: {e}")
        return JsonResponse({"error": "Could not create payment session."}, status=500)


@csrf_exempt
def stripe_webhook_view(request):
    """
    Handles incoming webhooks from Stripe to update subscription status.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # Invalid payload
        print(f"Webhook error: Invalid payload. {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:  # type: ignore # Suppress persistent Pylance error
        # Invalid signature
        print(f"Webhook error: Invalid signature. {e}")
        return HttpResponse(status=400)
    # Catch generic Stripe errors
    except stripe.StripeError as e:  # Use base StripeError
        print(f"Webhook error: Stripe API error during construct_event. {e}")
        return HttpResponse(status=400)
    except Exception as e:
        print(f"Webhook error: Non-Stripe exception during construct_event. {e}")
        return HttpResponse(status=500)  # Use 500 for unexpected server errors

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"Webhook received: checkout.session.completed for session {session.id}")

        # Retrieve the session details WITH expanded subscription object
        try:
            # It's generally recommended to retrieve the object again from Stripe API
            # to ensure you have the latest state, though expanding is often sufficient.
            session_with_line_items = stripe.checkout.Session.retrieve(
                session.id, expand=["line_items", "subscription"]
            )
            # line_items = session_with_line_items.line_items # If needed

            # Extract metadata or customer ID to find the user
            django_user_id = session.metadata.get("django_user_id")
            stripe_customer_id = session.customer
            # Subscription object is expanded, access it directly
            subscription = (
                session_with_line_items.subscription
            )  # Get subscription object
            stripe_subscription_id = None  # Initialize
            subscription_status = (
                "incomplete"  # Default status if no subscription found
            )

            # Explicitly check if subscription object exists and is the correct type
            if isinstance(subscription, StripeSubscription):
                stripe_subscription_id = subscription.id
                subscription_status = (
                    subscription.status  # type: ignore  <- Add type ignore if Pylance still complains
                )  # Should be 'trialing' or 'active'
            else:
                # This case is unlikely if checkout completed for a subscription
                print(
                    f"Webhook Warning: No subscription object found or expanded for completed session {session.id}"
                )

            user = None
            if django_user_id:
                try:
                    user = CustomUser.objects.get(id=django_user_id)
                except CustomUser.DoesNotExist:
                    print(f"Webhook Error: User with ID {django_user_id} not found.")
            elif stripe_customer_id:
                # Less reliable if customer ID wasn't saved yet, but good fallback
                try:
                    user = CustomUser.objects.get(stripe_customer_id=stripe_customer_id)
                except CustomUser.DoesNotExist:
                    print(
                        f"Webhook Error: User with Stripe Customer ID {stripe_customer_id} not found."
                    )

            if user:
                # Update user's subscription details upon checkout completion
                user.subscription_tier = "pro"
                user.stripe_subscription_id = stripe_subscription_id
                # Ensure Stripe Customer ID is saved
                if not user.stripe_customer_id and stripe_customer_id:
                    user.stripe_customer_id = stripe_customer_id

                # Set status based on the expanded subscription object (already determined above)
                user.subscription_status = subscription_status

                # Determine tier based on line items (MUST DO THIS HERE)
                price_id = None
                try:
                    # Add more robust checking for nested objects
                    if (
                        session_with_line_items.line_items
                        and session_with_line_items.line_items.data
                        and len(session_with_line_items.line_items.data) > 0
                        and session_with_line_items.line_items.data[0].price
                    ):
                        price_id = session_with_line_items.line_items.data[0].price.id
                    else:
                        print(
                            f"Webhook Warning: Could not find price ID in line items for session {session.id}"
                        )

                except AttributeError as e:
                    print(
                        f"Webhook Error: Attribute error accessing price ID in session {session.id}: {e}"
                    )
                    # Handle error appropriately, maybe set tier to None or log

                # Set tier based on the determined price_id
                if price_id == settings.STRIPE_BASIC_PRICE_ID:
                    user.subscription_tier = "basic"
                elif price_id == settings.STRIPE_PRO_PRICE_ID:
                    user.subscription_tier = "pro"
                else:
                    # Fallback or error
                    user.subscription_tier = (
                        None  # Explicitly set to None if price_id is unknown or missing
                    )
                    print(
                        f"Webhook Warning/Error: Could not determine tier from price_id '{price_id}' in session {session.id}"
                    )

                user.save()

                # Session variable clearing is removed as it's no longer needed

                print(
                    f"User {user.email} completed Pro checkout via webhook. Status: {user.subscription_status}"  # Updated log message slightly
                )
            else:
                print(
                    "Webhook Error: Could not identify user from checkout.session.completed."
                )

        except stripe.StripeError as e:  # Use base StripeError
            # Catch specific Stripe errors during processing
            print(f"Webhook Stripe API Error (checkout.session.completed): {e}")
            return HttpResponse(
                status=400
            )  # Indicate error processing event with Stripe
        except CustomUser.DoesNotExist:
            # Handle case where user lookup fails after getting ID
            print(
                f"Webhook Error: User lookup failed for ID {django_user_id} or customer {stripe_customer_id}."
            )
            return HttpResponse(status=404)  # Not Found
        except Exception as e:
            # Catch other unexpected errors during processing
            print(f"Webhook Generic Error (checkout.session.completed): {e}")
            return HttpResponse(status=500)  # Internal Server Error

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        print(
            f"Webhook received: customer.subscription.updated for subscription {subscription['id']}"  # Use key access
        )
        stripe_customer_id = subscription["customer"]  # Use key access
        stripe_subscription_id = subscription["id"]  # Use key access
        status = subscription["status"]  # Use key access

        try:
            user = CustomUser.objects.get(stripe_customer_id=stripe_customer_id)

            # Update status and potentially tier based on the new status
            user.subscription_status = status
            user.stripe_subscription_id = stripe_subscription_id  # Ensure it's current

            # Determine tier based on the price ID in the subscription items
            new_tier = None
            try:
                if subscription.get("items") and subscription["items"].get("data"):
                    sub_price_id = subscription["items"]["data"][0]["price"]["id"]
                    if sub_price_id == settings.STRIPE_BASIC_PRICE_ID:
                        new_tier = "basic"
                    elif sub_price_id == settings.STRIPE_PRO_PRICE_ID:
                        new_tier = "pro"
                    else:
                        print(
                            f"Webhook Warning: Unknown price ID {sub_price_id} in updated subscription {stripe_subscription_id}"
                        )
            except (KeyError, IndexError, AttributeError) as e:
                print(
                    f"Webhook Error: Could not extract price ID from updated subscription {stripe_subscription_id}: {e}"
                )

            if status == "active" and new_tier:
                # If it becomes active (e.g., post-trial payment success or reactivation)
                user.subscription_tier = new_tier
            elif status in ["past_due", "incomplete", "unpaid"]:
                # Keep the existing tier, just update status. Tier only changes on active or cancellation.
                pass  # Tier remains what it was
            elif status == "canceled":
                # Subscription is canceled (but might still be usable until period end if cancel_at_period_end was used)
                # The 'customer.subscription.deleted' event handles final cleanup.
                # We might set tier to None here or wait for deletion event. Let's wait.
                pass  # Keep tier for now, status is 'canceled'

            user.save()
            print(
                f"User {user.email} subscription updated. Status: {status}, Tier: {user.subscription_tier}"
            )
        except CustomUser.DoesNotExist:
            print(
                f"Webhook Error: User with Stripe Customer ID {stripe_customer_id} not found for subscription update."
            )
            return HttpResponse(status=404)  # Not Found
        except stripe.StripeError as e:  # Use base StripeError
            print(f"Webhook Stripe API Error (customer.subscription.updated): {e}")
            return HttpResponse(status=400)
        except Exception as e:
            print(f"Webhook Generic Error (customer.subscription.updated): {e}")
            return HttpResponse(status=500)

    elif event["type"] == "customer.subscription.deleted":
        # This event fires when a subscription is definitively canceled (immediately or at period end).
        subscription = event["data"]["object"]
        print(
            f"Webhook received: customer.subscription.deleted for subscription {subscription['id']}"  # Use key access
        )
        stripe_customer_id = subscription["customer"]  # Use key access
        try:
            user = CustomUser.objects.get(stripe_customer_id=stripe_customer_id)
            # Don't set tier to 'free'. Status indicates cancellation.
            user.subscription_tier = (
                None  # Or keep the last active tier? Setting to None for clarity.
            )
            user.subscription_status = "canceled"  # Status from the event itself might be slightly different, but 'canceled' is clear.
            user.stripe_subscription_id = None  # Clear subscription ID
            user.save()
            print(f"User {user.email} subscription definitively canceled via webhook.")
        except CustomUser.DoesNotExist:
            print(
                f"Webhook Error: User with Stripe Customer ID {stripe_customer_id} not found for subscription deletion."
            )
            return HttpResponse(status=404)  # Not Found
        except stripe.StripeError as e:  # Use base StripeError
            print(f"Webhook Stripe API Error (customer.subscription.deleted): {e}")
            return HttpResponse(status=400)
        except Exception as e:
            print(f"Webhook Generic Error (customer.subscription.deleted): {e}")
            return HttpResponse(status=500)

    # ... handle other relevant event types as needed

    return HttpResponse(status=200)


# @login_required # Decorator already present
def payment_success_view(request):
    """Handles the display of the success page after payment."""
    # Logic for handling pending signup removed, as users are now logged in before payment.
    # This view now only handles the success case for already logged-in users.

    # Optional: Verify session_id from Stripe if needed for extra confirmation,
    # but the webhook should be the primary source of truth for status updates.
    # session_id = request.GET.get('session_id')
    # if session_id:
    #     try:
    #         checkout_session = stripe.checkout.Session.retrieve(session_id)
    #         # Check session status, customer, etc. if necessary
    #     except stripe.error.StripeError as e:
    #         messages.error(request, f"Error verifying payment session: {e}")
    #         return redirect('some_error_page_or_dashboard')

    # Make message more generic as this view handles initial success and upgrades
    messages.success(request, "Subscription process successful!")
    # Consider redirecting to dashboard or settings instead of rendering a static page
    return redirect("brain_dump_list")  # Redirect to dashboard after success
    # return render(request, "subscriptions_app/payment_success.html", context) # Old way


# @login_required # Decorator already present
def payment_cancel_view(request):
    """Handles the display of the cancellation page."""
    # Logic for handling pending signup cancellation removed.
    # This view now only handles cancellation for already logged-in users.
    messages.warning(request, "Upgrade process canceled.")
    # Redirect logged-in user back to upgrade page or maybe dashboard/settings
    return redirect("subscriptions_app:upgrade_page")


@login_required
@require_POST  # Ensure this view only accepts POST requests
def cancel_subscription_view(request):
    """
    Handles the cancellation of a user's Stripe subscription.
    """
    user = request.user

    if not user.stripe_subscription_id:
        messages.error(request, "You do not have an active subscription to cancel.")
        return redirect(reverse("settings"))  # Redirect back to settings

    try:
        # Modify the subscription to cancel at the end of the current period
        stripe.Subscription.modify(
            user.stripe_subscription_id, cancel_at_period_end=True
        )

        # The webhook 'customer.subscription.updated' will likely fire to update the status
        # and 'customer.subscription.deleted' will fire when it's actually canceled by Stripe.
        # No immediate user model update needed here.

        messages.success(
            request,
            "Your subscription has been set to cancel at the end of the current billing period. You will retain access until then.",
        )

    except stripe.StripeError as e:  # Corrected base Stripe error
        # Handle potential Stripe API errors
        messages.error(
            request,
            f"There was an error canceling your subscription: {e}. Please contact support.",
        )
        print(f"Stripe Error canceling subscription for {user.email}: {e}")

    except Exception as e:
        # Handle other unexpected errors
        messages.error(
            request,
            "An unexpected error occurred. Please try again or contact support.",
        )
        print(f"Unexpected Error canceling subscription for {user.email}: {e}")

    return redirect(reverse("settings"))  # Redirect back to settings page


@login_required
@require_POST  # Ensure this view only accepts POST requests
def reactivate_subscription_view(request):
    """
    Handles the reactivation of a user's Stripe subscription that was set to cancel at period end.
    """
    user = request.user

    if not user.stripe_subscription_id:
        messages.error(request, "You do not have a subscription to reactivate.")
        # Redirect to upgrade page as they might want to start a new one
        return redirect(reverse("subscriptions_app:upgrade_page"))

    try:
        # Retrieve the subscription to ensure it exists and check its status
        subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)

        # Check if it's actually set to cancel at period end
        if not subscription.cancel_at_period_end:
            messages.warning(
                request, "Your subscription is not currently scheduled to cancel."
            )
            return redirect(
                reverse("subscriptions_app:upgrade_page")
            )  # Or settings page

        # Modify the subscription to remove the cancel_at_period_end flag
        stripe.Subscription.modify(
            user.stripe_subscription_id, cancel_at_period_end=False
        )

        # The webhook 'customer.subscription.updated' should fire shortly after this
        # to reflect the change in Stripe's system. No immediate user model update needed here.

        messages.success(
            request, "Your subscription has been reactivated successfully!"
        )

    except (
        stripe.InvalidRequestError
    ) as e:  # Corrected: Access error directly from stripe module
        # Handle cases like the subscription already being inactive or canceled
        if "No such subscription" in str(e):
            messages.error(
                request,
                "Could not find your subscription. It might already be canceled.",
            )
            # Clear local data if Stripe says it doesn't exist? Risky without webhook confirmation.
        else:
            messages.error(
                request,
                f"There was an error reactivating your subscription: {e}. Please contact support.",
            )
        print(
            f"Stripe InvalidRequestError reactivating subscription for {user.email}: {e}"
        )

    except stripe.StripeError as e:  # Catch other Stripe errors
        messages.error(
            request,
            f"There was a Stripe error reactivating your subscription: {e}. Please contact support.",
        )
        print(f"Stripe Error reactivating subscription for {user.email}: {e}")

    except Exception as e:
        # Handle other unexpected errors
        messages.error(
            request,
            "An unexpected error occurred during reactivation. Please contact support.",
        )
        print(f"Unexpected Error reactivating subscription for {user.email}: {e}")

    # Redirect back to the upgrade page to show the updated status
    return redirect(reverse("subscriptions_app:upgrade_page"))
