# populate the URL patterns for the brain dump app

from django.urls import path
from .views import (
    brain_dump_view,
    brain_dump_list,
    brain_dump_detail,
    brain_dump_update,
    create_post,
    save_post,
    twitter_connect,
    twitter_callback,
    twitter_disconnect,
    twitter_connect_oauth1,  # Added for OAuth 1.0a
    twitter_callback_oauth1,  # Added for OAuth 1.0a
    post_list,
    post_detail,
    settings_view,
    chat_view,  # Import the new view
)

urlpatterns = [
    path("", brain_dump_view, name="brain_dump"),
    path("brain-dumps/", brain_dump_list, name="brain_dump_list"),
    path("brain-dump/<uuid:dump_id>/", brain_dump_detail, name="brain_dump_detail"),
    path(
        "brain-dump/<uuid:dump_id>/update/", brain_dump_update, name="brain_dump_update"
    ),
    path("create-post/", create_post, name="create_post"),
    path("save-post/", save_post, name="save_post"),
    path("posts/", post_list, name="posts"),
    path("posts/<uuid:post_id>/", post_detail, name="post_detail"),
    # OAuth 2.0 URLs
    path("twitter/connect/", twitter_connect, name="twitter_connect"),
    path("twitter/callback/", twitter_callback, name="twitter_callback"),
    # OAuth 1.0a URLs
    path(
        "twitter/connect_oauth1/", twitter_connect_oauth1, name="twitter_connect_oauth1"
    ),
    path(
        "twitter/callback_oauth1/",
        twitter_callback_oauth1,
        name="twitter_callback_oauth1",
    ),
    # Common disconnect URL (can be used for both, as it just deletes the TwitterConnection object)
    path("twitter/disconnect/", twitter_disconnect, name="twitter_disconnect"),
    path("settings/", settings_view, name="settings"),
    path("chat/", chat_view, name="chat"),  # Add the chat URL pattern
]
