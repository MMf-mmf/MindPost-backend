from django.urls import path
from . import views

app_name = "subscriptions_app"

urlpatterns = [
    path("upgrade/", views.upgrade_page_view, name="upgrade_page"),
    path(
        "create-checkout-session/",
        views.create_checkout_session_view,
        name="create_checkout_session",
    ),
    path("webhook/", views.stripe_webhook_view, name="stripe_webhook"),
    path("payment-success/", views.payment_success_view, name="payment_success"),
    path("payment-cancel/", views.payment_cancel_view, name="payment_cancel"),
    path(
        "cancel-subscription/",
        views.cancel_subscription_view,
        name="cancel_subscription",
    ),
    path(
        "reactivate-subscription/",
        views.reactivate_subscription_view,
        name="reactivate_subscription",
    ),
]
