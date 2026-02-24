import stripe  # Add stripe import
import datetime  # Add datetime import
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse  # Added HttpResponse
from django.template.loader import render_to_string  # Added render_to_string
from django.views.decorators.http import require_http_methods
import json, nh3, logging, os, tweepy, uuid, shutil
from .models import BrainDump, Post, OAuthState, TwitterConnection
from .tasks import transcribe_audio_file, generate_embedding, generate_post
from django.db.models.functions import TruncDate
from django.core.files.storage import default_storage  # For saving temporary files
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from .models import PostImage  # Import PostImage model
from utils.convert_audio import convert_audio_to_mp3
from subscriptions_app.decorators import limit_check  # Import the decorator
from subscriptions_app.utils import (
    check_recording_length,
    check_usage,
    get_user_limits,
)  # Import utils & get_user_limits
from mutagen.mp3 import MP3  # To get audio duration
import math  # For ceiling duration
from django.core.files.base import ContentFile  # For handling file objects


from .x_api import (
    create_tweet_v2,
    refresh_oauth2_token,
)
from django.http import (
    HttpResponseRedirect,
)
from django.contrib.auth.decorators import (
    login_required,
)  # Ensure login_required is imported
from .tasks import generate_chat_response  # Import the helper function

logger = logging.getLogger("project")
stripe.api_key = settings.STRIPE_SECRET_KEY  # Initialize Stripe


@login_required
@require_http_methods(["GET"])
def brain_dump_list(request):
    """
    View to display list of brain dumps for the current user, grouped by day.
    """
    # Get all brain dumps for the current user, annotate with date
    all_brain_dumps = (
        BrainDump.objects.filter(user=request.user)
        .annotate(date=TruncDate("created_at"))
        .order_by("-date", "-created_at")
    )

    # Get the per_page parameter from the request, default to 10
    per_page = request.GET.get("per_page", 10)

    # Validate per_page to be an integer between 10 and 50
    try:
        per_page = int(per_page)
        if per_page < 10:
            per_page = 10
        elif per_page > 50:
            per_page = 50
    except (TypeError, ValueError):
        per_page = 10

    # Set up pagination with the user-selected per_page value
    paginator = Paginator(all_brain_dumps, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Group the paginated results by date
    grouped_dumps = {}
    for dump in page_obj:
        date_str = dump.created_at.date()
        if date_str not in grouped_dumps:
            grouped_dumps[date_str] = []
        grouped_dumps[date_str].append(dump)

    return render(
        request,
        "brain_dump_app/list.html",
        {
            "page_obj": page_obj,
            "grouped_dumps": grouped_dumps,
        },
    )


@login_required
@require_http_methods(["GET"])
def brain_dump_detail(request, dump_id):
    """
    View to display details of a specific brain dump.
    """
    brain_dump = get_object_or_404(BrainDump, id=dump_id, user=request.user)
    return render(request, "brain_dump_app/detail.html", {"brain_dump": brain_dump})


@login_required
@require_http_methods(["POST"])
def brain_dump_update(request, dump_id):
    """Update a brain dump's transcript."""
    brain_dump = get_object_or_404(BrainDump, id=dump_id, user=request.user)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)

        # Update the transcription
        brain_dump.transcription = nh3.clean(data.get("transcription", ""))
        brain_dump.edited = True

        # Save the brain dump to update the transcription
        brain_dump.save(update_fields=["transcription", "edited"])

        # Update tags from transcription
        # tags = brain_dump.update_tags_from_transcription()

        # If using vector embeddings, regenerate the embedding for the updated text
        try:
            # Generate new embedding for the updated transcription
            from .tasks import generate_embedding

            generate_embedding(dump_id=brain_dump.id)
        except Exception as e:
            logger.error(f"Error regenerating embedding: {e}")

        # Return success response with tags
        # return JsonResponse({"success": True, "tags": list(brain_dump.tags.names())})
        return JsonResponse({"success": True})
    except Exception as e:
        logger.error(f"Error updating brain dump: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
@limit_check("max_recording")  # Apply decorator for recording count limit
def brain_dump_view(request):
    """
    View to handle brain dump recording interface and file uploads.
    GET: Returns the recording interface
    POST: Handles audio file upload and transcription
    """
    if request.method == "GET":
        # Get the most recent brain dump for this user
        recent_dump = (
            BrainDump.objects.filter(
                user=request.user,
                transcription__isnull=False,
                transcription__gt="",  # Ensure it has actual content
            )
            .order_by("-created_at")
            .first()
        )
        user_limits = get_user_limits(request.user)
        context = {
            "recent_dump": recent_dump,
            "user": request.user,  # Pass the user object for current usage
            "user_limits": user_limits,  # Pass the limits dictionary
        }
        return render(request, "brain_dump_app/record.html", context)

    # Handle POST request (file upload)
    duration_minutes = 0  # Initialize duration
    mp3_file_object = None  # Initialize converted file object

    try:
        if "audio_file" not in request.FILES:
            messages.error(request, "No audio file provided")
            return render(
                request,
                "brain_dump_app/record.html",
                {"recent_dump": None, "error": "No audio file provided"},
            )

        original_audio = request.FILES["audio_file"]
        original_audio.seek(0)  # Ensure pointer is at the start

        # --- Convert Audio and Check Length ---
        try:
            # Convert the audio to MP3 format first
            # convert_audio_to_mp3 should return a file-like object (e.g., ContentFile)
            mp3_file_object = convert_audio_to_mp3(original_audio)
            if not mp3_file_object:
                raise Exception("Audio conversion failed.")

            # Check duration using mutagen - it needs a file path or file-like object
            try:
                # If it's a ContentFile or similar in-memory object
                mp3_file_object.seek(0)  # Reset pointer
                audio_info = MP3(mp3_file_object)
                duration_seconds = audio_info.info.length
                duration_minutes = duration_seconds / 60.0
            except Exception as mutagen_err:
                # Fallback if mutagen can't read the file-like object directly
                # This might happen depending on how convert_audio_to_mp3 is implemented
                # If convert_audio_to_mp3 returned a path, this part wouldn't be needed
                # If convert_audio_to_mp3 returns a path string:
                # audio_info = MP3(mp3_file_object) # Assuming mp3_file_object is the path
                # duration_seconds = audio_info.info.length
                # duration_minutes = duration_seconds / 60.0
                # else:
                raise Exception(f"Could not determine duration: {mutagen_err}")
            # Check length against user limits
            if not check_recording_length(request.user, duration_minutes):
                messages.error(
                    request,
                    f"Recording length ({duration_minutes:.1f} min) exceeds your limit.",
                )
                return render(
                    request,
                    "brain_dump_app/record.html",
                    {"recent_dump": None, "error": "Recording too long"},
                )

            # Reset pointer again for saving/transcription
            mp3_file_object.seek(0)

        except Exception as e:
            logger.error(
                f"Error converting audio or checking duration: {str(e)}", exc_info=True
            )
            messages.error(request, f"Error processing audio: {str(e)}")
            return render(
                request,
                "brain_dump_app/record.html",
                {"recent_dump": None, "error": "Error processing audio"},
            )
        # --- End Convert & Check ---

        # Create new BrainDump instance without saving yet
        brain_dump = BrainDump(
            recording=mp3_file_object,  # Use the converted file object
            user=request.user,
            transcription="",  # Will be populated by transcription
        )

        # Transcribe the audio file during upload
        transcription = transcribe_audio_file(
            mp3_file_object
        )  # Use the converted file object
        if transcription:
            brain_dump.transcription = transcription
            # now generate the embedding
            embedding = generate_embedding(dump_id=None, transcription=transcription)
            if embedding:
                brain_dump.embedding = embedding
            else:
                logger.error(
                    f"Failed to generate embedding for the transcription of user {request.user.email}"
                )
        else:
            # Handle transcription failure? Maybe still save the dump?
            logger.warning(f"Transcription failed for user {request.user.email}")
            # Optionally add a message: messages.warning(request, "Audio recorded, but transcription failed.")

        # Now save the BrainDump with transcription (or without if failed)
        brain_dump.save()

        # Extract and save hashtags after transcription
        # if transcription:
        #     brain_dump.update_tags_from_transcription()

        # Success message and redirect
        messages.success(request, "Your brain dump was successfully recorded.")
        return redirect("brain_dump_detail", dump_id=brain_dump.id)

    except Exception as e:
        # Catch any other unexpected errors during the POST processing
        logger.error(f"Error processing audio upload: {str(e)}", exc_info=True)
        messages.error(request, "There was an error processing your recording.")
        return render(
            request,
            "brain_dump_app/record.html",
            {"recent_dump": None, "error": "Server error processing upload"},
        )


@login_required
@require_http_methods(["POST"])
@limit_check("max_post_generations")  # Apply decorator
def create_post(request):
    """
    View to process selected brain dumps and create a post from them.
    """
    selected_ids = request.POST.get("selected_ids", "")
    min_chars = request.POST.get("min_chars", 0)
    max_chars = request.POST.get("max_chars", 280)

    if not selected_ids:
        messages.error(request, "No brain dumps were selected.")
        return redirect("brain_dump_list")

    # Parse the comma-separated IDs and filter for this user's brain dumps
    try:
        id_list = [id_str for id_str in selected_ids.split(",")]
        brain_dumps = BrainDump.objects.filter(id__in=id_list, user=request.user)
        # If some IDs weren't found or don't belong to the user
        if len(brain_dumps) != len(id_list):
            messages.warning(request, "Some selected brain dumps could not be found.")
            # Proceed with the ones found? Or return error? Let's proceed.
            if not brain_dumps.exists():
                messages.error(
                    request, "No valid brain dumps found for post generation."
                )
                return redirect("brain_dump_list")

        # Call the generate_post function with the selected brain dumps
        posts_json = generate_post(
            brain_dumps, post_type="twitter", min_chars=min_chars, max_chars=max_chars
        )
        posts = json.loads(posts_json)

        # --- Increment Usage Counter ---
        try:
            user = request.user
            user.current_post_generations += 1
            user.save(update_fields=["current_post_generations"])
            logger.info(
                f"Usage updated for user {user.email}: post_generations={user.current_post_generations}"
            )
        except Exception as e:
            logger.error(
                f"Failed to update post generation counter for user {request.user.email}: {e}",
                exc_info=True,
            )
        # --- End Increment ---

        # --- Get User's Twitter Char Limit ---
        char_limit = 280  # Default limit
        try:
            twitter_connection = TwitterConnection.objects.get(user=request.user)
            char_limit = twitter_connection.char_limit
        except TwitterConnection.DoesNotExist:
            pass  # Use default limit if not connected
        except Exception as e:
            logger.error(
                f"Error fetching Twitter char limit for user {request.user.email}: {e}"
            )
            # Use default limit on error
        # --- End Get Char Limit ---

        # Render the post creation template with the selected brain dumps and char limit
        return render(
            request,
            "brain_dump_app/create_post.html",
            {
                "brain_dumps": brain_dumps,
                "posts": posts,
                "char_limit": char_limit,  # Pass the limit to the template
            },
        )

    except (ValueError, TypeError):
        messages.error(request, "Invalid selection data.")
        return redirect("brain_dump_list")
    except Exception as e:
        logger.error(f"Error generating post: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred while generating the post.")
        return redirect("brain_dump_list")


@login_required
@require_http_methods(["POST"])
def save_post(request):
    """
    View to save a post as draft, publish it, or delete it.
    """
    action = request.POST.get("action", "draft")
    title = request.POST.get(
        "title", ""
    ).strip()  # Title not currently used in Post model
    content = request.POST.get("content", "").strip()
    brain_dump_ids = request.POST.get("brain_dump_ids", "")
    post_id_from_request = request.POST.get(
        "post_id"
    )  # Use a different name to avoid conflict

    # Validate required fields
    if not content:
        messages.error(request, "Post content cannot be empty.")
        return redirect("brain_dump_list")

    if action == "delete" and not post_id_from_request:
        messages.error(request, "Cannot delete a post that doesn't exist.")
        return redirect("brain_dump_list")

    # Handle edit mode (post_id provided)
    post_instance = None  # Renamed from 'post' to avoid confusion
    is_new_post = True
    if post_id_from_request:
        is_new_post = False
        try:
            # Get existing post
            post_instance = get_object_or_404(
                Post, id=post_id_from_request, user=request.user
            )
        except:  # Catch Http404 specifically?
            messages.error(
                request, "Post not found or you don't have permission to edit it."
            )
            return redirect("brain_dump_list")

    # Handle delete action
    if action == "delete" and post_instance:
        post_instance.delete()
        messages.success(request, "Post has been deleted.")
        return redirect("brain_dump_list")  # Or maybe post_list?

    # Set status based on action
    target_status = Post.POSTED if action == "publish" else Post.DRAFT

    # --- Check Usage Limit for Publishing ---
    # Only check if publishing a *new* post or updating an existing *draft* to published
    should_check_publish_limit = False
    if target_status == Post.POSTED:
        if is_new_post:
            should_check_publish_limit = True
        elif (
            post_instance and post_instance.status == Post.DRAFT
        ):  # Check if post_instance exists
            should_check_publish_limit = True

    if should_check_publish_limit:
        if not check_usage(request.user, "max_post_submissions"):
            error_message = (
                "Post submission limit reached. Save as draft or upgrade your plan."
            )
            messages.error(error_message)
            return redirect("brain_dump_list")
    # --- End Check Usage Limit ---

    # Get associated brain dumps if IDs provided
    brain_dumps = []
    if brain_dump_ids:
        try:
            id_list = [id_str for id_str in brain_dump_ids.split(",")]
            brain_dumps = list(
                BrainDump.objects.filter(id__in=id_list, user=request.user)
            )
        except Exception as e:
            logger.error(f"Error processing brain dump IDs: {str(e)}")
            # Non-fatal, continue without association

    # Create or update the post
    if post_instance:
        # Update existing post
        post_instance.content = content
        post_instance.status = target_status
        post_instance.save()  # Save changes before potential Twitter post

        # --- Handle Image Uploads for Existing Post ---
        uploaded_images = request.FILES.getlist("images")
        temp_files = []  # Track temp files for cleanup later
        media_paths = []  # Will store paths to temp files for Twitter

        if uploaded_images:
            import tempfile
            import os

            for img_file in uploaded_images:
                # Basic validation
                if img_file.content_type.startswith("image"):
                    # Create PostImage object
                    post_image = PostImage.objects.create(
                        post=post_instance, image=img_file
                    )

                    # Simultaneously create temp file for Twitter upload
                    try:
                        # Determine extension from content type or filename
                        file_ext = os.path.splitext(img_file.name)[1]
                        if not file_ext:
                            # Fallback to guessing extension from content type
                            if (
                                "jpeg" in img_file.content_type
                                or "jpg" in img_file.content_type
                            ):
                                file_ext = ".jpg"
                            elif "png" in img_file.content_type:
                                file_ext = ".png"
                            else:
                                file_ext = ".img"  # Generic fallback

                        # Create temp file
                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=file_ext, delete=False
                        )

                        # Need to reset the file pointer since Django may have read it already
                        img_file.seek(0)

                        # Write image data to temp file
                        for chunk in img_file.chunks():
                            temp_file.write(chunk)
                        temp_file.close()

                        # Track the temp file
                        temp_files.append(temp_file.name)
                        media_paths.append(temp_file.name)

                        logger.info(
                            f"Created temp file for Twitter upload: {temp_file.name}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error creating temp file from uploaded image: {str(e)}"
                        )
                else:
                    messages.warning(
                        request, f"Skipped non-image file: {img_file.name}"
                    )
        # --- End Handle Image Uploads ---

    else:
        # Create new post
        post_instance = Post.objects.create(
            user=request.user,
            content=content,
            status=target_status,
            post_type="twitter",  # Default type, could be made selectable
        )
        # Save the new post instance first to get an ID
        post_instance.save()

        # --- Handle Image Uploads for New Post ---
        uploaded_images = request.FILES.getlist("images")
        temp_files = []  # Track temp files for cleanup later
        media_paths = []  # Will store paths to temp files for Twitter

        if uploaded_images:
            import tempfile
            import os

            for img_file in uploaded_images:
                # Basic validation
                if img_file.content_type.startswith("image"):
                    # Create PostImage object
                    post_image = PostImage.objects.create(
                        post=post_instance, image=img_file
                    )

                    # Simultaneously create temp file for Twitter upload
                    try:
                        # Determine extension from content type or filename
                        file_ext = os.path.splitext(img_file.name)[1]
                        if not file_ext:
                            # Fallback to guessing extension from content type
                            if (
                                "jpeg" in img_file.content_type
                                or "jpg" in img_file.content_type
                            ):
                                file_ext = ".jpg"
                            elif "png" in img_file.content_type:
                                file_ext = ".png"
                            else:
                                file_ext = ".img"  # Generic fallback

                        # Create temp file
                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=file_ext, delete=False
                        )

                        # Need to reset the file pointer since Django may have read it already
                        img_file.seek(0)

                        # Write image data to temp file
                        for chunk in img_file.chunks():
                            temp_file.write(chunk)
                        temp_file.close()

                        # Track the temp file
                        temp_files.append(temp_file.name)
                        media_paths.append(temp_file.name)

                        logger.info(
                            f"Created temp file for Twitter upload: {temp_file.name}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error creating temp file from uploaded image: {str(e)}"
                        )
                else:
                    messages.warning(
                        request, f"Skipped non-image file: {img_file.name}"
                    )
        # --- End Handle Image Uploads ---

    # Associate brain dumps with the post (works for new or existing)
    if brain_dumps:
        try:
            post_instance.brain_dump.add(*brain_dumps)
        except AttributeError:
            logger.warning(
                f"Post model might not have 'brain_dump' ManyToManyField setup correctly for post ID {post_instance.id}"
            )
        except Exception as e:
            logger.error(
                f"Error associating brain dumps with post {post_instance.id}: {e}"
            )

    # If publishing, attempt to publish to Twitter/X
    # Check target_status and if it doesn't already have a twitter post_id
    if target_status == Post.POSTED and not post_instance.post_id:
        published_to_twitter = False

        try:
            # For existing posts, we still need to create temp files if none were created during upload
            if (
                not media_paths
                and post_instance.id
                and hasattr(post_instance, "images")
            ):
                # --- Create Temporary Files from Post Images ---
                post_images = post_instance.images.all()[:4]

                if post_images:
                    import tempfile
                    import os
                    import shutil

                    for post_image in post_images:
                        if (
                            post_image.image and post_image.image.name
                        ):  # Check for name instead of path
                            try:
                                # Create a temporary file with same extension
                                file_ext = os.path.splitext(post_image.image.name)[1]
                                if not file_ext:
                                    file_ext = ".jpg"  # Default extension

                                # Create unique temp file
                                temp_file = tempfile.NamedTemporaryFile(
                                    suffix=file_ext, delete=False
                                )
                                temp_path = temp_file.name
                                temp_file.close()  # Close the file so we can write to it

                                # Use storage.open() instead of direct file path access
                                with post_image.image.storage.open(
                                    post_image.image.name, "rb"
                                ) as source_file:
                                    with open(temp_path, "wb") as dest_file:
                                        shutil.copyfileobj(source_file, dest_file)

                                # Add to our lists for tracking and sending to Twitter
                                media_paths.append(temp_path)
                                temp_files.append(temp_path)

                                logger.info(
                                    f"Created temp file for Twitter upload: {temp_path}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error creating temp file from image: {str(e)}"
                                )
            # --- End Create Temporary Files ---

            twitter_connection = TwitterConnection.objects.get(user=request.user)

            # Check if access token is valid, refresh if needed
            if not twitter_connection.is_access_valid:
                if twitter_connection.oauth2_refresh_token:
                    try:
                        new_tokens = refresh_oauth2_token(
                            request.user,
                            twitter_connection.oauth2_refresh_token,
                            twitter_connection=twitter_connection,
                        )
                        if not new_tokens:
                            raise Exception("Token refresh failed.")
                    except Exception as e:
                        logger.error(
                            f"Error refreshing Twitter token: {str(e)}", exc_info=True
                        )
                        messages.warning(
                            request,
                            "Your Twitter authorization needs to be renewed. Post saved as draft.",
                        )
                        post_instance.status = Post.DRAFT  # Revert status
                        post_instance.save(update_fields=["status"])
                        return redirect("brain_dump_list")  # Or post detail?
                else:
                    messages.warning(
                        request,
                        "Your Twitter connection is invalid. Post saved as draft.",
                    )
                    post_instance.status = Post.DRAFT  # Revert status
                    post_instance.save(update_fields=["status"])
                    return redirect("brain_dump_list")  # Or post detail?

            # At this point we should have a valid access token
            response = create_tweet_v2(
                user=request.user,
                text=content,
                media_paths=media_paths,  # Pass the list of temporary file paths
            )
            # Check if response is not None and has data before accessing
            if (
                response  # Check if response exists
                and "id" in response  # Check if 'id' is in response.data (dict)
            ):

                post_instance.post_id = response["id"]  # Now safe to access
                post_instance.save(update_fields=["post_id"])  # Save twitter ID
                published_to_twitter = True
                messages.success(request, "Post has been published to Twitter/X.")
            else:
                messages.warning(
                    request,
                    "Post saved but could not be published to Twitter/X at this time. Make sure that you are properly connected and that you post is not longer then the allowed character limit on your account.",
                )
                logger.warning(
                    f"Twitter API did not return expected data or failed for user {request.user.email}, post ID {post_instance.id}. Response: {response}"  # Log the actual response
                )
                post_instance.status = Post.DRAFT  # Revert status
                post_instance.save(update_fields=["status"])

        except TwitterConnection.DoesNotExist:
            messages.warning(
                request,
                "Post saved as draft. Please connect your Twitter account to publish.",
            )
            post_instance.status = Post.DRAFT  # Revert status
            post_instance.save(update_fields=["status"])

        except Exception as e:
            logger.error(f"Error publishing to Twitter/X: {str(e)}", exc_info=True)
            messages.warning(
                request, f"Post saved but error publishing to Twitter/X: {str(e)[:100]}"
            )
        finally:
            # --- Clean up temporary files ---
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Removed temporary file: {temp_file}")
                except Exception as e:
                    logger.error(f"Error removing temporary file {temp_file}: {str(e)}")
            # --- End Cleanup ---

        # --- Increment Usage Counter if Published Successfully ---
        if published_to_twitter or (
            target_status == Post.POSTED
            and should_check_publish_limit
            and not published_to_twitter
        ):
            if should_check_publish_limit:  # Double check it passed the initial check
                try:
                    user = request.user
                    user.current_post_submissions += 1
                    user.save(update_fields=["current_post_submissions"])
                    logger.info(
                        f"Usage updated for user {user.email}: post_submissions={user.current_post_submissions}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to update post submission counter for user {request.user.email}: {e}",
                        exc_info=True,
                    )
        # --- End Increment ---

    else:
        messages.success(
            request, f"Post has been saved as {post_instance.get_status_display()}."  # type: ignore
        )

    return redirect(
        "post_detail", post_id=post_instance.id
    )  # Redirect to the detail view of the saved/published post


@login_required
def twitter_connect(request):
    """
    Initiate the Twitter OAuth 2.0 flow with PKCE.
    Generate auth URL and store state parameters in database.
    """
    try:
        # Configure OAuth2 handler
        oauth2_handler = tweepy.OAuth2UserHandler(
            client_id=settings.TWITTER_CLIENT_ID,
            redirect_uri=request.build_absolute_uri(reverse("twitter_callback")),
            scope=["tweet.read", "tweet.write", "users.read", "offline.access"],
            client_secret=settings.TWITTER_CLIENT_SECRET,
        )

        # Get the authorization URL - this internally generates state and code_verifier
        auth_url = oauth2_handler.get_authorization_url()

        # Extract state from the URL
        from urllib.parse import urlparse, parse_qs

        parsed_url = urlparse(auth_url)
        state = parse_qs(parsed_url.query)["state"][0]
        # Get code_verifier from the tweepy OAuth2UserHandler
        code_verifier = oauth2_handler._client.code_verifier  # type: ignore

        # Store OAuth state in database
        redirect_uri = request.build_absolute_uri(reverse("twitter_callback"))
        expires_at = timezone.now() + datetime.timedelta(minutes=10)

        OAuthState.objects.create(
            user=request.user,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
        )

        # Save return path if specified
        next_url = request.GET.get("next")
        if next_url:
            request.session["twitter_oauth_next"] = next_url

        # Redirect to Twitter's authorization page
        return HttpResponseRedirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating Twitter OAuth flow: {str(e)}", exc_info=True)
        messages.error(request, f"Error connecting to Twitter: {str(e)[:100]}")
        return redirect("brain_dump_list")


@login_required
def twitter_callback(request):
    """
    Handle the callback from Twitter OAuth 2.0 authorization.
    Exchange the code for tokens and store the connection.
    """
    # Get state and code from the request
    state = request.GET.get("state")
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        messages.error(request, f"Twitter authorization failed: {error}")
        return redirect("brain_dump_list")

    if not state or not code:
        messages.error(request, "Invalid response from Twitter. Missing parameters.")
        return redirect("brain_dump_list")

    try:
        # Retrieve the stored OAuth state
        oauth_state = get_object_or_404(
            OAuthState, state=state, user=request.user, used=False
        )

        # Validate the state
        if not oauth_state.is_valid:
            messages.error(request, "Authorization session expired. Please try again.")
            return redirect("brain_dump_list")

        # Mark the state as used
        oauth_state.used = True
        oauth_state.save()

        # Set up the OAuth handler with stored parameters
        oauth2_handler = tweepy.OAuth2UserHandler(
            client_id=settings.TWITTER_CLIENT_ID,
            redirect_uri=oauth_state.redirect_uri,
            scope=["tweet.read", "tweet.write", "users.read", "offline.access"],
            client_secret=settings.TWITTER_CLIENT_SECRET,
        )

        # Manually set the code_verifier from our database
        oauth2_handler._client.code_verifier = oauth_state.code_verifier  # type: ignore

        # Exchange code for access token
        # We need to build the full authorization response URL
        auth_response_url = request.build_absolute_uri()
        token_data = oauth2_handler.fetch_token(auth_response_url)

        # Create a client using the bearer token - FIXED THIS LINE
        # For OAuth 2.0, we should use bearer_token parameter instead of the default constructor
        client = tweepy.Client(bearer_token=token_data["access_token"])

        user_info = client.get_me(
            user_auth=False,
            user_fields=["name", "username", "verified", "verified_type"],
        )

        # Calculate token expiration time
        expires_in = token_data.get("expires_in", 7200)
        # Get expires_at directly if available (preferred)
        expires_at_timestamp = token_data.get("expires_at")
        # if expires_at_timestamp:
        #     expires_at_dt = datetime.datetime.fromtimestamp(
        #         expires_at_timestamp, tz=datetime.timezone.utc
        #     )
        # else:
        #     # Calculate from expires_in if expires_at is not provided
        #     expires_at_dt = timezone.now() + datetime.timedelta(seconds=expires_in)

        verified = False  # Default to False
        twitter_user_id = None
        twitter_username = None
        twitter_name = None

        # Safely access user_info data and attributes
        if user_info and hasattr(user_info, "data") and user_info.data:
            user_data = user_info.data
            twitter_user_id = str(user_data.get("id")) if user_data.get("id") else None
            twitter_username = user_data.get("username")
            twitter_name = user_data.get("name")
            verified_type = user_data.get("verified_type")
            is_verified_legacy = user_data.get(
                "verified", False
            )  # Legacy verified status

            if verified_type in [
                "blue",
                "business",
                "government",  # Added government as per potential types
                "premium",
            ]:
                verified = True
            elif is_verified_legacy:  # Fallback to legacy verified status if needed
                verified = True

        # Save or update the Twitter connection
        twitter_connection, created = TwitterConnection.objects.update_or_create(
            user=request.user,
            defaults={
                "oauth2_access_token": token_data["access_token"],
                "oauth2_refresh_token": token_data.get("refresh_token", ""),
                "expires_in": expires_in,  # Keep expires_in for reference
                "expires_at": expires_at_timestamp,  # Store calculated datetime
                "token_type": token_data.get("token_type", "bearer"),
                "scope": token_data.get("scope", ""),
                "twitter_user_id": twitter_user_id,
                "twitter_username": twitter_username,
                "twitter_name": twitter_name,
                "verified": verified,
                "char_limit": (
                    settings.X_POST_LIMIT_PRO
                    if verified
                    else settings.X_POST_LIMIT_FREE
                ),
            },
        )

        messages.success(
            request,
            f"Successfully connected Twitter account @{twitter_username}",
        )

        # Redirect to settings page with status
        return redirect(reverse("settings") + "?connection_status=success")

    except OAuthState.DoesNotExist:
        messages.error(
            request, "Invalid authorization state. Please try connecting again."
        )
        return redirect(reverse("settings") + "?connection_status=error")
    except Exception as e:
        logger.error(f"Error completing Twitter OAuth flow: {str(e)}", exc_info=True)
        messages.error(request, f"Error connecting to Twitter: {str(e)[:100]}")
        return redirect(reverse("settings") + "?connection_status=error")


@login_required
def twitter_connect_oauth1(request):
    """
    Initiate the Twitter OAuth 1.0a flow.
    """
    try:
        # Get the callback URL for OAuth 1.0a
        callback_url = request.build_absolute_uri(reverse("twitter_callback_oauth1"))

        # Configure OAuth1 handler
        # Ensure TWITTER_CONSUMER_KEY and TWITTER_CONSUMER_SECRET are in settings
        oauth1_handler = tweepy.OAuth1UserHandler(
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            callback=callback_url,
        )

        # Get authorization URL and request token
        auth_url = oauth1_handler.get_authorization_url(signin_with_twitter=True)

        # Store request token in session
        request.session["oauth1_request_token"] = oauth1_handler.request_token

        # Save return path if specified
        next_url = request.GET.get("next")
        if next_url:
            request.session["twitter_oauth_next"] = (
                next_url  # Consider a different session key if needed
            )

        return HttpResponseRedirect(auth_url)

    except tweepy.TweepyException as e:
        logger.error(
            f"Error initiating Twitter OAuth 1.0a flow (TweepyException): {str(e)}",
            exc_info=True,
        )
        messages.error(request, f"Error connecting to Twitter (OAuth1): {str(e)[:100]}")
        return redirect(
            request.GET.get("next", "settings")
        )  # Redirect to 'next' or 'settings'
    except Exception as e:
        logger.error(
            f"Error initiating Twitter OAuth 1.0a flow: {str(e)}", exc_info=True
        )
        messages.error(request, f"Error connecting to Twitter (OAuth1): {str(e)[:100]}")
        return redirect(request.GET.get("next", "settings"))


@login_required
def twitter_callback_oauth1(request):
    """
    Handle the callback from Twitter OAuth 1.0a authorization.
    """
    oauth_verifier = request.GET.get("oauth_verifier")
    # oauth_token is also returned but often not directly used if request_token is in session
    # oauth_token_from_twitter = request.GET.get("oauth_token") # This is the request token

    if not oauth_verifier:
        messages.error(request, "OAuth verifier not found in callback.")
        return redirect(request.session.pop("twitter_oauth_next", "settings"))

    # Retrieve request token from session
    request_token_dict = request.session.pop("oauth1_request_token", None)
    if not request_token_dict:
        messages.error(
            request, "OAuth 1.0a session expired or invalid. Please try again."
        )
        return redirect(request.session.pop("twitter_oauth_next", "settings"))

    try:
        # Re-initialize OAuth1 handler (callback not strictly needed here but good practice)
        callback_url = request.build_absolute_uri(reverse("twitter_callback_oauth1"))
        oauth1_handler = tweepy.OAuth1UserHandler(
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            callback=callback_url,
        )
        # Set the retrieved request token
        oauth1_handler.request_token = request_token_dict

        # Get access token
        access_token, access_token_secret = oauth1_handler.get_access_token(
            oauth_verifier
        )

        # Use the access tokens to create an API client
        auth = tweepy.OAuth1UserHandler(
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        api_v1 = tweepy.API(auth)

        # Verify credentials and get user info
        user_info = api_v1.verify_credentials()

        twitter_user_id = user_info.id_str
        twitter_username = user_info.screen_name
        twitter_name = user_info.name
        # OAuth 1.0a doesn't typically return 'verified_type' directly like v2.
        # 'verified' boolean is usually available.
        verified = user_info.verified

        # Save or update the Twitter connection
        twitter_connection, created = TwitterConnection.objects.update_or_create(
            user=request.user,
            defaults={
                "oauth1_access_token": access_token,
                "oauth1_access_token_secret": access_token_secret,
                "twitter_user_id": twitter_user_id,
                "twitter_username": twitter_username,
                "twitter_name": twitter_name,
                "verified": verified,
                "char_limit": (
                    settings.X_POST_LIMIT_PRO
                    if verified
                    else settings.X_POST_LIMIT_FREE
                ),
                # Optionally clear OAuth2 tokens if OAuth1 is now primary, or add an auth_type field
                # "oauth2_access_token": None,
                # "oauth2_refresh_token": None,
                # "expires_in": None,
                # "expires_at": None,
                # "token_type": None, # Or set to 'oauth1'
                # "scope": None, # OAuth1 doesn't use scopes in the same way
            },
        )

        messages.success(
            request,
            f"Successfully connected Twitter account @{twitter_username} using OAuth 1.0a.",
        )
        return redirect(
            request.session.pop(
                "twitter_oauth_next",
                reverse("settings") + "?connection_status=success_oauth1",
            )
        )

    except tweepy.TweepyException as e:
        logger.error(
            f"Error completing Twitter OAuth 1.0a flow (TweepyException): {str(e)}",
            exc_info=True,
        )
        messages.error(request, f"Error connecting to Twitter (OAuth1): {str(e)[:100]}")
        return redirect(
            request.session.pop(
                "twitter_oauth_next",
                reverse("settings") + "?connection_status=error_oauth1",
            )
        )
    except Exception as e:
        logger.error(
            f"Error completing Twitter OAuth 1.0a flow: {str(e)}", exc_info=True
        )
        messages.error(request, f"Error connecting to Twitter (OAuth1): {str(e)[:100]}")
        return redirect(
            request.session.pop(
                "twitter_oauth_next",
                reverse("settings") + "?connection_status=error_oauth1",
            )
        )


@login_required
def twitter_disconnect(request):
    """
    Disconnect the user's Twitter account.
    """
    try:
        # Delete the Twitter connection for the user
        TwitterConnection.objects.filter(user=request.user).delete()
        messages.success(request, "Twitter account disconnected.")
    except Exception as e:
        logger.error(f"Error disconnecting Twitter account: {str(e)}", exc_info=True)
        messages.error(request, "Error disconnecting Twitter account.")

    # Redirect to settings page after disconnect
    return redirect("settings")


@login_required
def post_list(request):
    """
    View to display a list of posts for the current user.
    """
    # Get all posts for the current user
    all_posts = Post.objects.filter(user=request.user).order_by("-created_at")

    # Get the per_page parameter from the request, default to 10
    per_page = request.GET.get("per_page", 10)

    # Validate per_page to be an integer between 10 and 50
    try:
        per_page = int(per_page)
        if per_page < 10:
            per_page = 10
        elif per_page > 50:
            per_page = 50
    except (TypeError, ValueError):
        per_page = 10

    # Set up pagination with the user-selected per_page value
    paginator = Paginator(all_posts, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "brain_dump_app/post_list.html",
        {
            "page_obj": page_obj,
        },
    )


@login_required
def post_detail(request, post_id):
    """
    View to display details of a specific post.
    """
    post = get_object_or_404(Post, id=post_id, user=request.user)

    # --- Get User's Twitter Char Limit ---
    char_limit = 280  # Default limit
    try:
        twitter_connection = TwitterConnection.objects.get(user=request.user)
        char_limit = twitter_connection.char_limit
    except TwitterConnection.DoesNotExist:
        pass  # Use default limit if not connected
    except Exception as e:
        logger.error(
            f"Error fetching Twitter char limit for user {request.user.email}: {e}"
        )
        # Use default limit on error
    # --- End Get Char Limit ---

    return render(
        request,
        "brain_dump_app/post_detail.html",
        {
            "post": post,
            "char_limit": char_limit,  # Pass the limit to the template
        },
    )


@login_required
def settings_view(request):
    """
    View to display and manage user settings including social media connections and subscription status.
    """
    user = request.user
    subscription_cancel_at = None
    subscription_canceling = False  # Initialize
    twitter_connected = TwitterConnection.objects.filter(user=user).exists()

    if user.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
            if subscription.cancel_at_period_end and subscription.cancel_at:
                subscription_cancel_at = datetime.datetime.fromtimestamp(
                    subscription.cancel_at, tz=datetime.timezone.utc
                )
                subscription_canceling = True  # Set based on Stripe data
        except stripe.StripeError as e:
            logger.error(f"Error retrieving Stripe subscription for {user.email}: {e}")
            messages.warning(
                request, "Could not retrieve subscription details from Stripe."
            )
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving Stripe subscription for {user.email}: {e}"
            )
            messages.warning(
                request,
                "An unexpected error occurred while fetching subscription details.",
            )

    context = {
        "subscription_cancel_at": subscription_cancel_at,
        "twitter_connected": twitter_connected,
        "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
        "basic_price_id": settings.STRIPE_BASIC_PRICE_ID,
        "pro_price_id": settings.STRIPE_PRO_PRICE_ID,
        "subscription_canceling": subscription_canceling,
        "user_limits": get_user_limits(user),  # Also pass user_limits
    }
    return render(request, "brain_dump_app/settings.html", context)


@login_required
@limit_check("max_chat_messages")  # Apply decorator
def chat_view(request):
    """
    View to handle the chat interface using standard Django request/response.
    Manages chat history in the session.
    """
    # Initialize chat history in session if it doesn't exist
    chat_history = request.session.get("chat_history", [])

    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        if message:
            # Add user message to history FIRST
            chat_history.append({"sender": "user", "text": message})

            ai_response = "Sorry, an error occurred."  # Default AI response
            try:
                # Call the helper function directly
                response_data, status_code = generate_chat_response(
                    user=request.user, message=message
                )

                if status_code == 200:
                    ai_response = response_data.get(
                        "response", "Sorry, I couldn't process that."
                    )
                    # --- Increment Usage Counter ---
                    try:
                        user = request.user
                        user.current_chat_messages += 1
                        user.save(update_fields=["current_chat_messages"])
                        logger.info(
                            f"Usage updated for user {user.email}: chat_messages={user.current_chat_messages}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to update chat message counter for user {request.user.email}: {e}",
                            exc_info=True,
                        )
                    # --- End Increment ---

                elif status_code == 404:
                    ai_response = response_data.get(
                        "error", "No brain dumps found to search."
                    )
                else:  # Handle other error status codes from generate_chat_response
                    ai_response = response_data.get(
                        "error", "An error occurred during processing."
                    )

            except Exception as e:
                logger.error(
                    f"Error in chat view calling generate_chat_response: {e}",
                    exc_info=True,
                )
                ai_response = "Sorry, an internal server error occurred."

            # Add AI response to history
            chat_history.append({"sender": "assistant", "text": ai_response})

            # Save updated history to session
            request.session["chat_history"] = chat_history

            # --- HTMX Response ---
            if request.headers.get("HX-Request") == "true":
                # Get only the last two messages (user and AI)
                new_messages = (
                    chat_history[-2:] if len(chat_history) >= 2 else chat_history[-1:]
                )
                context = {"new_messages": new_messages}
                # Render the fragment template
                html_fragment = render_to_string(
                    "brain_dump_app/_chat_messages_fragment.html", context
                )
                return HttpResponse(html_fragment)
            # --- End HTMX Response ---
            else:
                # Standard Django: Redirect after POST to prevent re-submission
                return redirect("chat")

    # For GET requests or initial load
    user_limits = get_user_limits(request.user)
    context = {
        "chat_history": chat_history,
        "user": request.user,
        "user_limits": user_limits,
    }
    return render(request, "brain_dump_app/chat.html", context)
