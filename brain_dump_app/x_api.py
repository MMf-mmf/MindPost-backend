import tweepy
from django.conf import settings
import logging
import os
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
import requests
import tempfile

from brain_dump_app.models import TwitterConnection

logger = logging.getLogger("project")

# if debug is on
if settings.DEBUG:
    # Force allow OAuth over HTTP in development
    # IMPORTANT: This should only be enabled in development!
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


def create_tweet_v2(
    user,  # Changed from access_token to user object
    text,
    media_paths=None,
    media_urls=None,
):
    """
    Create a new tweet using Twitter API v2 with optional media upload.

    Args:
        user (User): The Django User object initiating the tweet.
        text (str): The text content of the tweet.
        media_paths (list, optional): List of paths to image files to upload with the tweet.
        media_urls (list, optional): List of URLs to images to upload with the tweet.

    Returns:
        dict: The created tweet data if successful, or an error dict if failed.
    """
    try:
        twitter_conn = TwitterConnection.objects.get(user=user)
    except TwitterConnection.DoesNotExist:
        logger.error(f"TwitterConnection not found for user {user.id}")
        return {"error": "Twitter connection not found for this user."}

    access_token = twitter_conn.oauth2_access_token
    if not access_token:
        logger.error(f"No OAuth 2.0 access token found for user {user.id}")
        return {"error": "OAuth 2.0 access token not found."}

    client = tweepy.Client(bearer_token=access_token)

    media_ids = []
    temp_files = []  # Track temp files to clean up later
    api = None  # Will be initialized if media is present and OAuth 1.0a is available

    # Check if media upload is attempted
    if media_paths or media_urls:
        if not (
            twitter_conn.oauth1_access_token and twitter_conn.oauth1_access_token_secret
        ):
            logger.error(
                f"User {user.id} attempted media upload without OAuth 1.0a credentials."
            )
            return {
                "error": "OAuth 1.0a authentication is required to upload media. Please re-authenticate with X/Twitter."
            }

        # Initialize API with user's OAuth 1.0a credentials for media upload
        auth = tweepy.OAuth1UserHandler(
            settings.TWITTER_API_KEY,  # App's consumer key
            settings.TWITTER_API_SECRET,  # App's consumer secret
            twitter_conn.oauth1_access_token,  # User's access token
            twitter_conn.oauth1_access_token_secret,  # User's access token secret
        )
        api = tweepy.API(auth)

    try:
        # Handle URLs by downloading to temp files first (Twitter API doesn't accept direct URLs)
        if media_urls and api:

            # Ensure media_urls is a list
            if isinstance(media_urls, str):
                media_urls = [media_urls]

            for url in media_urls:
                try:
                    logger.info(f"Downloading media from URL: {url}")

                    # Download the image from URL
                    response = requests.get(url, stream=True, timeout=15)
                    if response.status_code != 200:
                        logger.error(
                            f"Failed to download image from {url}: HTTP {response.status_code}"
                        )
                        continue

                    # Create a temporary file with appropriate extension
                    file_ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                    temp_file = tempfile.NamedTemporaryFile(
                        suffix=file_ext, delete=False
                    )
                    temp_file_path = temp_file.name

                    # Write the content to the temp file
                    with open(temp_file_path, "wb") as f:
                        f.write(response.content)

                    # Track the file for cleanup
                    temp_files.append(temp_file_path)

                    # Now upload the temp file to Twitter
                    logger.info(
                        f"Uploading downloaded media as {temp_file_path} for user {user.id}"
                    )
                    media = api.media_upload(temp_file_path)  # api is now user-specific
                    media_ids.append(media.media_id)
                    logger.info(
                        f"Media uploaded successfully with ID: {media.media_id} for user {user.id}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing media URL {url} for user {user.id}: {str(e)}",
                        exc_info=True,
                    )
                    # Continue with other media URLs

        # Handle direct file paths
        if media_paths and api:
            # Ensure media_paths is a list
            if isinstance(media_paths, str):
                media_paths = [media_paths]

            # Upload each media file
            for media_path in media_paths:
                try:
                    # Upload the media
                    logger.info(
                        f"Uploading media from path: {media_path} for user {user.id}"
                    )
                    media = api.media_upload(media_path)  # api is now user-specific
                    media_ids.append(media.media_id)
                    logger.info(
                        f"Media uploaded successfully with ID: {media.media_id} for user {user.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error uploading media {media_path} for user {user.id}: {str(e)}"
                    )
                    # Continue with other media files

        # If media was intended but API was not initialized (e.g. no OAuth 1.0a creds),
        # this check ensures we don't proceed with a tweet that's missing its media.
        # The error for missing OAuth 1.0a creds would have been returned earlier.
        # This is more of a safeguard.
        if (media_urls or media_paths) and not api:
            logger.warning(
                f"Media upload was requested for user {user.id} but API for media upload was not initialized. This shouldn't happen if OAuth 1.0a check is correct."
            )
            # The actual error about missing OAuth 1.0a should have been returned already.
            # If somehow it gets here, it means the tweet will be sent without media.

        # Create the tweet (with media if available)
        if media_ids:
            print(
                f"Creating tweet for user {user.id} with text and media IDs: {media_ids}"
            )
            logger.info(
                f"Creating tweet for user {user.id} with text and media IDs: {media_ids}"
            )
            response = client.create_tweet(
                text=text,
                media_ids=media_ids,
                user_auth=False,  # user_auth=False because client is initialized with bearer token
            )
        else:
            print(f"Creating tweet for user {user.id} with text")
            logger.info(f"Creating tweet for user {user.id} with text")
            response = client.create_tweet(
                text=text, user_auth=False
            )  # user_auth=False

        return response.data  # Return the data part of the response
    except tweepy.TweepyException as e:
        logger.error(
            f"Error creating tweet for user {user.id}: {str(e)}", exc_info=True
        )
        # Try to parse a more specific error message from Tweepy if possible
        error_message = str(e)
        if e.response is not None and hasattr(e.response, "text"):
            try:
                error_details = e.response.json()
                if "errors" in error_details and error_details["errors"]:
                    error_message = error_details["errors"][0].get("message", str(e))
                elif "detail" in error_details:
                    error_message = error_details["detail"]
            except ValueError:  # Not a JSON response
                pass
        return {"error": f"Twitter API error: {error_message}"}
    except Exception as e:  # Catch any other unexpected errors
        logger.error(
            f"Unexpected error in create_tweet_v2 for user {user.id}: {str(e)}",
            exc_info=True,
        )
        return {"error": f"An unexpected error occurred: {str(e)}"}
    finally:
        # Clean up temp files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Removed temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_file}: {str(e)}")


def refresh_oauth2_token(user, refresh_token, twitter_connection=None):
    """
    Refresh an expired OAuth2 token using a refresh token and update the model if provided.

    Args:
        refresh_token (str): The refresh token from the original OAuth flow
        twitter_connection (TwitterConnection, optional): The model to update

    Returns:
        dict: New token information including access_token and refresh_token
    """
    try:
        # Create an OAuth2Session with your client credentials
        oauth2_session = OAuth2Session(settings.TWITTER_CLIENT_ID)

        # Twitter's token refresh endpoint
        token_url = "https://api.twitter.com/2/oauth2/token"

        # Refreshing the token requires client authentication
        auth = HTTPBasicAuth(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET)

        # Make the token refresh request
        new_tokens = oauth2_session.refresh_token(
            token_url,
            refresh_token=refresh_token,
            auth=auth,
            client_id=settings.TWITTER_CLIENT_ID,
        )

        # Prepare token data
        token_data = {
            "access_token": new_tokens.get("access_token"),
            "refresh_token": new_tokens.get(
                "refresh_token", refresh_token
            ),  # Use original if not provided
            "expires_in": new_tokens.get("expires_in", 7200),
            "token_type": new_tokens.get("token_type", "bearer"),
            "scope": new_tokens.get("scope", ""),
        }

        # Calculate expiration timestamp if not provided
        if "expires_at" not in new_tokens and "expires_in" in new_tokens:
            import time

            token_data["expires_at"] = time.time() + new_tokens["expires_in"]
        else:
            token_data["expires_at"] = new_tokens.get("expires_at")

        # Update the TwitterConnection model if provided
        if twitter_connection:
            twitter_connection.oauth2_access_token = token_data["access_token"]
            twitter_connection.oauth2_refresh_token = token_data["refresh_token"]
            twitter_connection.expires_in = token_data["expires_in"]
            twitter_connection.expires_at = token_data["expires_at"]
            twitter_connection.token_type = token_data["token_type"]
            twitter_connection.scope = token_data["scope"]
            twitter_connection.save()
            logger.info(
                f"Updated Twitter connection for user ID {twitter_connection.user_id}"
            )

            # Fetch user info after refreshing token
            try:
                client = tweepy.Client(bearer_token=token_data["access_token"])
                user_info = client.get_me(
                    user_auth=False,
                    user_fields=["name", "username", "verified", "verified_type"],
                )

                # Update TwitterConnection with verification and char limit
                verified = False
                if hasattr(
                    user_info.data, "verified_type"
                ) and user_info.data.verified_type in [
                    "blue",
                    "business",
                    "premium",
                ]:
                    verified = True
                elif hasattr(user_info.data, "verified") and user_info.data.verified:
                    verified = True

                if twitter_connection:
                    twitter_connection.verified = verified
                    twitter_connection.twitter_username = user_info.data.username
                    twitter_connection.char_limit = (
                        settings.X_POST_LIMIT_PRO
                        if verified
                        else settings.X_POST_LIMIT_FREE
                    )
                    twitter_connection.save(update_fields=["verified", "char_limit"])

            except Exception as e:
                logger.error(
                    f"Error fetching user info after token refresh: {str(e)}",
                    exc_info=True,
                )

        return token_data

    except Exception as e:
        logger.error(f"Error refreshing OAuth2 token: {str(e)}", exc_info=True)
        return None


# OLDER HARD CODED WORKING VERSION
# import tweepy
# from django.conf import settings
# import logging


# logger = logging.getLogger("project")


# def create_tweet_v2(
#     text,
#     api_key=None,
#     api_secret=None,
#     access_token=None,
#     access_secret=None,
#     bearer_token=None,
# ):
#     """
#     Create a new tweet using Twitter API v2.

#     Args:
#         text (str): The text content of the tweet
#         bearer_token (str, optional): Twitter API v2 Bearer Token
#         api_key (str, optional): Twitter API key
#         api_secret (str, optional): Twitter API secret
#         access_token (str, optional): Twitter access token
#         access_secret (str, optional): Twitter access token secret

#     Returns:
#         dict: The created tweet data if successful
#     """
#     # For write operations, we need OAuth 1.0a User Context authentication
#     if api_key and api_secret and access_token and access_secret:
#         # Use OAuth 1.0a authentication for write operations
#         client = tweepy.Client(
#             consumer_key=api_key,
#             consumer_secret=api_secret,
#             access_token=access_token,
#             access_token_secret=access_secret,
#         )
#     elif bearer_token:
#         # Bearer token alone can't post tweets, but we'll try with the client
#         client = tweepy.Client(bearer_token=bearer_token)
#         print("Warning: Bearer token alone may not be sufficient for posting tweets")
#     else:
#         print("Error: Authentication credentials not provided")
#         return None

#     try:
#         # Create the tweet
#         response = client.create_tweet(text=text)
#         return response
#     except tweepy.TweepyException as e:
#         print(f"Error creating tweet: {e}")
#         return None


# # Example usage:
# # To use this function, you'll need to add your Twitter API credentials with write permissions
# # response = create_tweet_v2(
# #     text="Test Pong!",
# #     api_key=settings.API_KEY,
# #     api_secret=settings.API_SECRET,
# #     access_token=settings.ACCESS_TOKEN,
# #     access_secret=settings.ACCESS_SECRET,
# #     # bearer_token=X_API_KEY_BEARER_KEY,
# # )

# # if response and response.data:
# #     print(f"Tweet created with ID: {response.data['id']}")
