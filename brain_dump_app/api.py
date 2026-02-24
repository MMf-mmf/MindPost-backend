from rest_framework import serializers, viewsets, status, views
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from .models import BrainDump, Post, TwitterConnection, PostImage

# from taggit.serializers import TagListSerializerField, TaggitSerializer
from django.contrib.auth import get_user_model
import logging
from .tasks import (
    transcribe_audio_file,
    generate_embedding,
    generate_post,
    generate_chat_response,
)
import json
from .x_api import create_tweet_v2, refresh_oauth2_token
from subscriptions_app.decorators import limit_check  # Import the decorator

# Import all necessary utils
from subscriptions_app.utils import (
    check_recording_length,
    check_usage,
    check_and_reset_daily_limits,
)
from mutagen.mp3 import MP3  # To get audio duration
from utils.convert_audio import convert_audio_to_mp3  # Import conversion utility


User = get_user_model()
logger = logging.getLogger("project")


# Serializers
class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ["id", "image", "created_at"]  # 'image' will be the URL to the image
        read_only_fields = ["id", "created_at"]


class BrainDumpSerializer(serializers.ModelSerializer):
    # tags = serializers.SerializerMethodField()

    class Meta:
        model = BrainDump
        fields = ["id", "created_at", "transcription", "edited", "recording"]
        read_only_fields = ["id", "created_at", "edited", "recording"]

    # def get_tags(self, obj):
    #     return list(obj.tags.names())


class PostSerializer(serializers.ModelSerializer):
    images = PostImageSerializer(
        many=True, read_only=True
    )  # Assuming related_name='images' on PostImage.post

    class Meta:
        model = Post
        fields = [
            "id",
            "content",
            "created_at",
            "status",
            "post_id",
            "post_type",
            "images",
        ]
        read_only_fields = ["id", "created_at", "post_id", "images"]


class TwitterConnectionSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = TwitterConnection
        fields = ["twitter_username", "twitter_name", "connected_at", "is_valid"]
        read_only_fields = (
            [  # is_valid removed as it's explicitly a ReadOnlyField above
                "twitter_username",
                "twitter_name",
                "connected_at",
            ]
        )


# ViewSets
class BrainDumpViewSet(viewsets.ModelViewSet):
    """
    API endpoint for BrainDumps
    """

    serializer_class = BrainDumpSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return BrainDump.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """
        Handle POST request to create a new BrainDump with usage checks.
        """
        user = request.user
        audio_file = request.FILES.get("audio_file")
        duration_minutes = 0

        # --- Check and Reset Daily Limits ---
        check_and_reset_daily_limits(user)
        # --- End Check and Reset ---

        # --- Check Recording Count Limit ---
        if not check_usage(user, "max_recording"):
            return Response(
                {"detail": "Recording limit reached. Please upgrade your plan."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not audio_file:
            return Response(
                {"audio_file": "Audio file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Check Recording Length Limit & Convert ---
        mp3_file_object = None
        try:
            audio_file.seek(0)
            # Convert first to ensure we check the duration of the actual saved format (MP3)
            mp3_file_object = convert_audio_to_mp3(audio_file)
            if not mp3_file_object:
                raise serializers.ValidationError("Audio conversion to MP3 failed.")

            mp3_file_object.seek(0)
            audio_info = MP3(mp3_file_object)
            duration_seconds = audio_info.info.length
            duration_minutes = duration_seconds / 60.0

            if not check_recording_length(user, duration_minutes):
                raise serializers.ValidationError(
                    f"Recording length ({duration_minutes:.1f} min) exceeds your limit."
                )

            # Reset pointer for saving/transcription
            mp3_file_object.seek(0)

        except Exception as e:
            logger.error(
                f"API Error converting/checking duration: {str(e)}", exc_info=True
            )
            # Return DRF validation error
            raise serializers.ValidationError(f"Error processing audio: {str(e)}")
        # --- End Convert & Check ---

        # Proceed with standard DRF object creation via serializer
        # We need to pass the converted file and user to perform_create or handle saving here.
        # Handling transcription/embedding here after validation.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Save the instance manually first to get an ID if needed by tasks
            # Pass the *converted* mp3_file_object
            instance = serializer.save(
                user=user, recording=mp3_file_object, transcription=""
            )  # Save basic instance

            # Transcribe
            transcription = transcribe_audio_file(mp3_file_object)
            if transcription:
                instance.transcription = transcription
                # Generate embedding
                embedding = generate_embedding(
                    dump_id=instance.id, transcription=transcription
                )  # Use instance ID
                if embedding:
                    instance.embedding = embedding
                else:
                    logger.error(
                        f"API: Failed to generate embedding for user {user.email}, dump {instance.id}"
                    )
            else:
                logger.warning(f"API: Transcription failed for user {user.email}")

            # Save again with transcription/embedding
            instance.save()

            # Update tags
            # if transcription:
            #     instance.update_tags_from_transcription()

            headers = self.get_success_headers(serializer.data)
            # Use the serializer again to return the final state
            final_serializer = self.get_serializer(instance)
            return Response(
                final_serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        except Exception as e:
            logger.error(
                f"API Error during transcription/embedding/saving: {str(e)}",
                exc_info=True,
            )
            # Clean up instance if created? Depends on transaction management.
            # Return a generic server error
            return Response(
                {"detail": "Error processing brain dump after upload."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # perform_create is not needed as logic moved to create
    def perform_create(self, serializer):
        pass  # Logic moved to 'create'

    def update(self, request, *args, **kwargs):
        # Note: Updating doesn't consume usage limits in this design.
        # If editing should consume a limit, add checks here.
        brain_dump = self.get_object()
        # IF WE DECIDE TO ALLOW USERS TO ADD TAGS
        # tags = request.data.get("tags")
        # if tags:
        #     # Update tags if provided
        #     if tags and isinstance(tags, list):
        #         brain_dump.tags.set(tags)
        #     brain_dump.save(update_fields=["tags"])
        # Update transcription if provided
        transcription = request.data.get("transcription")
        if transcription:
            brain_dump.transcription = transcription
            brain_dump.edited = True
            brain_dump.save(update_fields=["transcription", "edited"])

            # Update tags
            # brain_dump.update_tags_from_transcription()

            # Regenerate embedding
            try:
                generate_embedding(dump_id=brain_dump.id)
            except Exception as e:
                logger.error(f"Error regenerating embedding: {e}")

        serializer = self.get_serializer(brain_dump)
        return Response(serializer.data)

    # @action(detail=False, methods=["get"])
    # def by_tag(self, request):
    #     """Get brain dumps filtered by tag"""
    #     tag = request.query_params.get("tag")
    #     if not tag:
    #         return Response(
    #             {"detail": "Tag parameter is required"},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     queryset = self.get_queryset().filter(tags__name__in=[tag])
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         serializer = self.get_serializer(page, many=True)
    #         return self.get_paginated_response(serializer.data)

    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)


class PostViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Posts
    """

    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _handle_uploaded_images(self, request, post_instance):
        logger.info(f"API: _handle_uploaded_images called for post {post_instance.id}.")
        logger.info(f"API: request.FILES content: {request.FILES}")
        uploaded_images = request.FILES.getlist(
            "media_files"
        )  # 'media_files' is the expected field name for multipart/form-data
        logger.info(
            f"API: Found {len(uploaded_images)} file(s) in request.FILES.getlist('media_files')."
        )

        processing_notes = []

        if not uploaded_images:
            logger.info("API: No files found under 'media_files' key in request.FILES.")
            processing_notes.append(
                "No image files were uploaded or found under the 'images' field."
            )

        for img_file in uploaded_images:
            file_name = getattr(img_file, "name", "Unknown Filename")
            content_type = getattr(img_file, "content_type", "Unknown ContentType")
            logger.info(
                f"API: Processing uploaded file: {file_name}, Content-Type: {content_type}"
            )

            # Check if it's an image file
            if hasattr(img_file, "content_type") and img_file.content_type.startswith(
                "image/"
            ):
                logger.info(
                    f"API: File {file_name} identified as an image. Attempting to save."
                )
                try:
                    created_post_image = PostImage.objects.create(
                        post=post_instance, image=img_file
                    )
                    logger.info(
                        f"API: Successfully created PostImage object with ID {created_post_image.id} for file {file_name}."
                    )
                    processing_notes.append(
                        f"Successfully processed image: {file_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"API: Error saving PostImage for post {post_instance.id}, file {file_name}: {str(e)}",
                        exc_info=True,  # Add exc_info for full traceback in logs
                    )
                    processing_notes.append(
                        f"Error saving image {file_name}: Could not process file. Details: {str(e)[:100]}"
                    )
            elif hasattr(img_file, "name"):  # If it has a name but isn't an image
                logger.warning(
                    f"API: Skipped non-image file: {file_name} (Content-Type: {content_type})"
                )
                processing_notes.append(f"Skipped non-image file: {file_name}")
            else:  # If it's some other kind of invalid file part
                logger.warning(
                    "API: Skipped an uploaded file part as it was not recognized or had no name."
                )
                processing_notes.append(
                    "Skipped an uploaded file as it was not recognized as an image or had no name."
                )
        logger.info(
            f"API: _handle_uploaded_images completed. Processing notes: {processing_notes}"
        )
        return processing_notes

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user).order_by("-created_at")

    def update(self, request, *args, **kwargs):
        """
        Handle PUT requests for Post objects with special handling for status changes
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Check if we're trying to change the status to POSTED
        old_status = instance.status
        new_status = request.data.get("status", old_status)

        # Handle image uploads first, regardless of status change, if images are part of the request
        image_processing_notes = self._handle_uploaded_images(request, instance)

        # If trying to change from non-POSTED to POSTED, use publishing logic
        if old_status != Post.POSTED and new_status == Post.POSTED:
            content = request.data.get("content", instance.content)
            # post_type = request.data.get("post_type", instance.post_type or "twitter") # Already part of instance

            # --- Check Usage Limit for Publishing ---
            if not check_usage(request.user, "max_post_submissions"):
                # Even if limit reached, save other changes as draft
                instance.content = content  # Save content changes
                # Apply other non-status, non-content changes from request.data if any
                for key, value in request.data.items():
                    if hasattr(instance, key) and key not in [
                        "status",
                        "content",
                        "post_id",
                        "images",
                    ]:
                        setattr(instance, key, value)
                instance.status = Post.DRAFT  # Force to draft
                instance.save()
                final_serializer_data = self.get_serializer(instance).data
                final_serializer_data["detail"] = (
                    "Post submission limit reached. Changes saved as draft."
                )
                if image_processing_notes:
                    final_serializer_data["image_processing_notes"] = (
                        image_processing_notes
                    )
                return Response(final_serializer_data, status=status.HTTP_403_FORBIDDEN)
            # --- End Check Usage Limit ---

            try:
                twitter_connection = TwitterConnection.objects.get(user=request.user)
                if not twitter_connection.is_access_valid:
                    if twitter_connection.oauth2_refresh_token:
                        new_tokens = refresh_oauth2_token(
                            request.user,
                            twitter_connection.oauth2_refresh_token,
                            twitter_connection=twitter_connection,
                        )
                        if not new_tokens:
                            raise Exception("Token refresh failed.")
                    else:
                        raise Exception("Twitter connection invalid, no refresh token.")

                # Prepare media_paths for Twitter (similar to views.py, needs temp files)
                # This is a simplified version for API; views.py has more robust temp file handling.
                media_paths = []
                # If PostImage objects exist and we want to send them to Twitter,
                # we'd need to create temporary local copies.
                # For now, this API update won't send existing images from PostImage to Twitter on update.
                # It will only send newly uploaded images if create_tweet_v2 is adapted or if we add temp file logic here.

                response = create_tweet_v2(
                    user=request.user, text=content, media_paths=media_paths
                )  # Pass empty media_paths for now

                if (
                    response
                    and hasattr(response, "data")
                    and response.data
                    and "id" in response.data
                ):
                    instance.post_id = response.data["id"]
                    instance.status = Post.POSTED
                    instance.content = content
                    # Apply other non-status, non-content changes
                    for key, value in request.data.items():
                        if hasattr(instance, key) and key not in [
                            "status",
                            "content",
                            "post_id",
                            "images",
                        ]:
                            setattr(instance, key, value)
                    instance.save()

                    try:  # Increment usage
                        user = request.user
                        user.current_post_submissions += 1
                        user.save(update_fields=["current_post_submissions"])
                    except Exception as e:
                        logger.error(
                            f"API: Failed to update post submission counter: {e}"
                        )

                    detail_message = "Successfully published to Twitter."
                else:
                    error_detail = "Failed to publish to Twitter."
                    if hasattr(response, "errors") and response.errors:
                        error_detail = f"Twitter error: {'; '.join([e.get('message', 'Unknown') for e in response.errors])}"

                    instance.status = Post.DRAFT  # Revert to draft on Twitter failure
                    instance.content = content  # Still save content
                    # Apply other non-status, non-content changes
                    for key, value in request.data.items():
                        if hasattr(instance, key) and key not in [
                            "status",
                            "content",
                            "post_id",
                            "images",
                        ]:
                            setattr(instance, key, value)
                    instance.save()
                    detail_message = f"{error_detail} Post remains as draft."

            except TwitterConnection.DoesNotExist:
                instance.status = Post.DRAFT
                instance.content = content
                for key, value in request.data.items():
                    if hasattr(instance, key) and key not in [
                        "status",
                        "content",
                        "post_id",
                        "images",
                    ]:
                        setattr(instance, key, value)
                instance.save()
                detail_message = "Twitter account not connected. Post remains as draft."
            except Exception as e:
                logger.error(
                    f"API: Unexpected error publishing post to Twitter: {str(e)}",
                    exc_info=True,
                )
                instance.status = Post.DRAFT
                instance.content = content
                for key, value in request.data.items():
                    if hasattr(instance, key) and key not in [
                        "status",
                        "content",
                        "post_id",
                        "images",
                    ]:
                        setattr(instance, key, value)
                instance.save()
                detail_message = f"Error publishing to Twitter: {str(e)[:100]}. Post remains as draft."

            final_serializer_data = self.get_serializer(instance).data
            final_serializer_data["detail"] = detail_message
            if image_processing_notes:
                final_serializer_data["image_processing_notes"] = image_processing_notes
            return Response(final_serializer_data, status=status.HTTP_200_OK)

        else:  # Standard update (not changing to POSTED, or already POSTED)
            # Apply all changes from request.data
            # The serializer will handle partial updates correctly if partial=True
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)  # This saves the instance

            if getattr(instance, "_prefetched_objects_cache", None):
                instance._prefetched_objects_cache = {}

            final_serializer_data = serializer.data
            if image_processing_notes:  # Add image notes if any
                final_serializer_data["image_processing_notes"] = image_processing_notes
            return Response(final_serializer_data)

    def partial_update(self, request, *args, **kwargs):
        """
        Handle PATCH requests with the same status change protection
        """
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):

        # Get data from request
        content = request.data.get("content")
        brain_dump_ids = request.data.get("brain_dump_ids", [])  # Ensure this is a list
        brain_dumps = None  # Initialize brain_dumps
        post_type = request.data.get("post_type", "twitter")
        status_value = request.data.get("status", Post.DRAFT)  # Default to DRAFT

        # Validate required fields
        if not content:
            return Response(
                {"detail": "Content is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # --- Check and Reset Daily Limits ---
        # Check before checking specific limits like publishing
        check_and_reset_daily_limits(request.user)
        # --- End Check and Reset ---

        # --- Check Usage Limit for Publishing ---
        should_increment_publish = False
        if status_value == Post.POSTED:
            if not check_usage(request.user, "max_post_submissions"):
                return Response(
                    {
                        "detail": "Post submission limit reached. Save as draft or upgrade your plan."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            should_increment_publish = True  # Mark for increment later if successful
        # --- End Check Usage Limit ---

        # Create new post instance (don't save yet if publishing to link IDs first)
        post = Post(user=request.user, content=content, post_type=post_type)
        # Don't set status yet if publishing - we'll set it after successful API call

        # For draft posts, save immediately
        if status_value == Post.DRAFT:
            post.status = Post.DRAFT
            post.save()

            # Associate brain dumps if IDs provided
            if brain_dump_ids:
                brain_dumps = BrainDump.objects.filter(
                    id__in=brain_dump_ids, user=request.user
                )
                if brain_dumps.exists():
                    try:
                        post.brain_dump.add(*brain_dumps)
                    except Exception as e:
                        logger.error(
                            f"API: Error associating brain dumps with draft post: {e}"
                        )
                        # Continue even if association fails
                else:
                    logger.warning(
                        f"API: No valid brain dumps found for IDs: {brain_dump_ids}"
                    )

            # Return the saved draft post
            image_processing_notes = self._handle_uploaded_images(request, post)
            final_serializer_data = self.get_serializer(post).data
            if image_processing_notes:
                final_serializer_data["image_processing_notes"] = image_processing_notes
            return Response(final_serializer_data, status=status.HTTP_201_CREATED)

        # If attempting to publish, handle Twitter/X API interactions
        if status_value == Post.POSTED:
            brain_dumps = None
            if brain_dump_ids:
                brain_dumps = BrainDump.objects.filter(
                    id__in=brain_dump_ids, user=request.user
                )

            try:
                # Get Twitter connection
                twitter_connection = TwitterConnection.objects.get(user=request.user)

                # Check if access token is valid
                if not twitter_connection.is_access_valid:
                    if twitter_connection.oauth2_refresh_token:
                        try:
                            new_tokens = refresh_oauth2_token(
                                request.user,
                                twitter_connection.oauth2_refresh_token,
                                twitter_connection=twitter_connection,
                            )
                            if not new_tokens:
                                # Save as draft with error message
                                post.status = Post.DRAFT
                                post.save()
                                if brain_dumps and brain_dumps.exists():
                                    post.brain_dump.add(*brain_dumps)

                                image_processing_notes = self._handle_uploaded_images(
                                    request, post
                                )  # Process images
                                final_serializer_data = self.get_serializer(post).data
                                if image_processing_notes:
                                    final_serializer_data["image_processing_notes"] = (
                                        image_processing_notes
                                    )
                                final_serializer_data["detail"] = (
                                    "Failed to refresh Twitter authorization. Post saved as draft."
                                )
                                return Response(
                                    final_serializer_data, status=status.HTTP_200_OK
                                )
                        except Exception as e:
                            logger.error(f"API: Error refreshing token: {str(e)}")
                            # Save as draft with error message
                            post.status = Post.DRAFT
                            post.save()
                            if brain_dumps and brain_dumps.exists():
                                post.brain_dump.add(*brain_dumps)

                            image_processing_notes = self._handle_uploaded_images(
                                request, post
                            )  # Process images
                            final_serializer_data = self.get_serializer(post).data
                            if image_processing_notes:
                                final_serializer_data["image_processing_notes"] = (
                                    image_processing_notes
                                )
                            final_serializer_data["detail"] = (
                                f"Twitter authorization error: {str(e)[:100]}. Post saved as draft."
                            )
                            return Response(
                                final_serializer_data, status=status.HTTP_200_OK
                            )
                    else:
                        # Save as draft with missing auth error
                        post.status = Post.DRAFT
                        post.save()
                        if brain_dumps and brain_dumps.exists():
                            post.brain_dump.add(*brain_dumps)

                        image_processing_notes = self._handle_uploaded_images(
                            request, post
                        )  # Process images
                        final_serializer_data = self.get_serializer(post).data
                        if image_processing_notes:
                            final_serializer_data["image_processing_notes"] = (
                                image_processing_notes
                            )
                        final_serializer_data["detail"] = (
                            "Twitter connection is no longer valid. Please reconnect your Twitter account. Post saved as draft."
                        )
                        return Response(
                            final_serializer_data, status=status.HTTP_200_OK
                        )

                # Attempt to publish to Twitter with valid token
                # For API, sending images to Twitter directly is more complex due to temp file handling.
                # The current views.py logic creates temp files. Replicating that here adds complexity.
                # For now, images are saved to PostImage, but not sent with the tweet via this API endpoint.
                # This could be a future enhancement if direct Twitter image posting via API is needed.
                media_paths = []  # Placeholder for future enhancement
                # If images were uploaded and processed, we could try to get their paths for Twitter.
                # However, PostImage stores them via Django's storage, not necessarily as local file paths
                # suitable for the current create_tweet_v2 which expects local paths.

                # The _handle_uploaded_images call will happen *after* the post is saved if successful.
                response = create_tweet_v2(
                    user=request.user, text=content, media_paths=media_paths
                )

                if (
                    response
                    and hasattr(response, "data")
                    and response.data
                    and "id" in response.data
                ):
                    # Successfully published to Twitter
                    post.post_id = response.data["id"]
                    post.status = Post.POSTED
                    post.save()

                    # Associate brain dumps
                    if brain_dumps and brain_dumps.exists():
                        try:
                            post.brain_dump.add(*brain_dumps)
                        except Exception as e:
                            logger.error(
                                f"API: Error associating brain dumps with published post: {e}"
                            )

                    # Increment usage counter on successful publish
                    try:
                        user = request.user
                        user.current_post_submissions += 1
                        user.save(update_fields=["current_post_submissions"])
                        logger.info(
                            f"API Usage updated for user {user.email}: post_submissions={user.current_post_submissions}"
                        )
                    except Exception as e:
                        logger.error(
                            f"API: Failed to update post submission counter for user {request.user.email}: {e}",
                            exc_info=True,
                        )

                    # Return successful result
                    image_processing_notes = self._handle_uploaded_images(
                        request, post
                    )  # Process images after successful save
                    final_serializer_data = self.get_serializer(post).data
                    if image_processing_notes:
                        final_serializer_data["image_processing_notes"] = (
                            image_processing_notes
                        )
                    final_serializer_data["detail"] = (
                        "Successfully published to Twitter."
                    )
                    return Response(
                        final_serializer_data, status=status.HTTP_201_CREATED
                    )
                else:
                    # Twitter API call failed but returned response
                    error_message = "Failed to publish to Twitter."
                    if hasattr(response, "errors") and response.errors:
                        error_details = "; ".join(
                            [e.get("message", "Unknown error") for e in response.errors]
                        )
                        error_message = f"Twitter error: {error_details}"

                    # Save as draft with error message
                    post.status = Post.DRAFT
                    post.save()  # Save before adding brain dumps or images
                    if brain_dumps and brain_dumps.exists():
                        post.brain_dump.add(*brain_dumps)

                    image_processing_notes = self._handle_uploaded_images(
                        request, post
                    )  # Process images
                    final_serializer_data = self.get_serializer(post).data
                    if image_processing_notes:
                        final_serializer_data["image_processing_notes"] = (
                            image_processing_notes
                        )
                    final_serializer_data["detail"] = (
                        error_message + " Post saved as draft."
                    )
                    return Response(final_serializer_data, status=status.HTTP_200_OK)

            except TwitterConnection.DoesNotExist:
                # No Twitter connection found
                post.status = Post.DRAFT
                post.save()  # Save before adding brain dumps or images
                if brain_dumps and brain_dumps.exists():
                    post.brain_dump.add(*brain_dumps)

                image_processing_notes = self._handle_uploaded_images(
                    request, post
                )  # Process images
                final_serializer_data = self.get_serializer(post).data
                if image_processing_notes:
                    final_serializer_data["image_processing_notes"] = (
                        image_processing_notes
                    )
                final_serializer_data["detail"] = (
                    "Twitter account not connected. Please connect your Twitter account first. Post saved as draft."
                )
                return Response(final_serializer_data, status=status.HTTP_200_OK)
            except Exception as e:
                # Unexpected error
                logger.error(
                    f"API: Unexpected error publishing post to Twitter: {str(e)}",
                    exc_info=True,
                )
                post.status = Post.DRAFT
                post.save()  # Save before adding brain dumps or images
                if brain_dumps and brain_dumps.exists():
                    post.brain_dump.add(*brain_dumps)

                image_processing_notes = self._handle_uploaded_images(
                    request, post
                )  # Process images
                final_serializer_data = self.get_serializer(post).data
                if image_processing_notes:
                    final_serializer_data["image_processing_notes"] = (
                        image_processing_notes
                    )
                final_serializer_data["detail"] = (
                    f"Error publishing to Twitter: {str(e)[:100]}. Post saved as draft."
                )
                return Response(final_serializer_data, status=status.HTTP_200_OK)

        # Fallback for unhandled status_value, though logic should cover DRAFT and POSTED
        # This part should ideally not be reached if status_value is validated or defaults correctly
        post.status = Post.DRAFT  # Default to saving as draft if status is unclear
        post.save()
        if brain_dumps and brain_dumps.exists():  # Ensure brain_dumps is defined
            post.brain_dump.add(*brain_dumps)
        image_processing_notes = self._handle_uploaded_images(request, post)
        final_serializer_data = self.get_serializer(post).data
        if image_processing_notes:
            final_serializer_data["image_processing_notes"] = image_processing_notes
        final_serializer_data["detail"] = (
            "Post processed, check status and image notes."  # Generic message
        )
        return Response(final_serializer_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    @limit_check("max_post_generations")  # Apply decorator
    def generate_from_dumps(self, request):
        """Generate post content from brain dumps"""
        brain_dump_ids = request.data.get(
            "brain_dump_uuids", []
        )  # Assuming UUIDs passed
        char_limit = 280  # Default for free Twitter/X accounts
        min_chars = request.data.get("min_chars", 0)  # Default to 0
        max_chars = request.data.get("max_chars", char_limit)

        # Get user's Twitter character limit (default to 280 if no connection exists)
        try:
            twitter_connection = TwitterConnection.objects.get(user=request.user)
            char_limit = twitter_connection.char_limit
        except TwitterConnection.DoesNotExist:
            # Use default 280 if no connection exists
            pass

        # Use the provided max_chars or the user's Twitter char_limit, whichever is lower
        # max_chars = min(
        #     max_chars_requested, char_limit
        # )  # Ensure we don't exceed user's limit

        if not brain_dump_ids:
            return Response(
                {"detail": "No brain dump UUIDs were provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Validate UUIDs if necessary
            valid_uuids = [
                bid for bid in brain_dump_ids if isinstance(bid, str)
            ]  # Basic check
            brain_dumps = BrainDump.objects.filter(
                id__in=valid_uuids, user=request.user
            )
            if not brain_dumps.exists():
                return Response(
                    {"detail": "No valid brain dumps found for the provided UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate post content from selected brain dumps
            posts_json = generate_post(
                brain_dumps,
                post_type="twitter",
                min_chars=min_chars,
                max_chars=max_chars,
            )
            posts = json.loads(posts_json)

            # --- Increment Usage Counter ---
            try:
                user = request.user
                user.current_post_generations += 1
                user.save(update_fields=["current_post_generations"])
                logger.info(
                    f"API Usage updated for user {user.email}: post_generations={user.current_post_generations}"
                )
            except Exception as e:
                logger.error(
                    f"API: Failed to update post generation counter for user {request.user.email}: {e}",
                    exc_info=True,
                )
            # --- End Increment ---

            # Include the user's character limit in the response
            return Response({"posts": posts, "char_limit": char_limit})
        except Exception as e:
            logger.error(f"API Error generating post: {str(e)}")
            return Response(
                {"detail": f"Error generating post: {str(e)[:100]}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TwitterConnectionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Twitter connection status
    """

    serializer_class = TwitterConnectionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return TwitterConnection.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def status(self, request):
        """Get Twitter connection status"""
        try:
            connection = TwitterConnection.objects.get(user=request.user)
            serializer = self.get_serializer(connection)
            # Use is_access_valid for immediate usability check
            return Response(
                {**serializer.data, "connected": connection.is_access_valid}
            )
        except TwitterConnection.DoesNotExist:
            return Response({"connected": False})

    @action(detail=False, methods=["delete"])
    def disconnect(self, request):
        """Disconnect Twitter account"""
        try:
            count, _ = TwitterConnection.objects.filter(user=request.user).delete()
            if count > 0:
                return Response(
                    {"status": "success", "message": "Twitter account disconnected"}
                )
            else:
                return Response(
                    {
                        "status": "not_found",
                        "message": "No Twitter account was connected.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Exception as e:
            logger.error(
                f"API: Error disconnecting Twitter account: {str(e)}", exc_info=True
            )
            return Response(
                {"status": "error", "message": "Error disconnecting Twitter account"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# API for obtaining JWT token is provided by Simple JWT automatically


class BrainDumpChatAPIView(views.APIView):
    """
    API endpoint for chatting with brain dumps using RAG
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # Apply limit check within the post method for APIView
    def post(self, request):
        user = request.user
        # --- Check and Reset Daily Limits ---
        check_and_reset_daily_limits(user)
        # --- End Check and Reset ---

        # --- Check Usage Limit ---
        if not check_usage(user, "max_chat_messages"):
            return Response(
                {"detail": "Chat message limit reached. Please upgrade your plan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # --- End Check ---

        # Get user's message from request
        message = request.data.get("message")
        if not message:
            return Response(
                {"detail": "Message is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use the helper function to generate the response
            response_data, status_code = generate_chat_response(
                user=request.user, message=message
            )

            # --- Increment Usage Counter on Success ---
            # Check status_code from the response tuple
            if status_code == status.HTTP_200_OK:
                try:
                    user.current_chat_messages += 1
                    user.save(update_fields=["current_chat_messages"])
                    logger.info(
                        f"API Usage updated for user {user.email}: chat_messages={user.current_chat_messages}"
                    )
                except Exception as e:
                    logger.error(
                        f"API: Failed to update chat message counter for user {user.email}: {e}",
                        exc_info=True,
                    )
            # --- End Increment ---

            return Response(response_data, status=status_code)

        except Exception as e:
            logger.error(f"API Error in brain dump chat: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while processing your request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AccountDeleteAPIView(views.APIView):
    """
    API endpoint for deleting user account - blacklists tokens and deactivates account
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        """
        Delete user account by blacklisting JWT tokens and setting account to inactive
        """
        user = request.user

        try:
            # Try to get the refresh token from the request
            refresh_token = request.data.get("refresh_token")
            breakpoint()
            if refresh_token:
                try:
                    # Create RefreshToken instance and blacklist it
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                    logger.info(
                        f"API: Successfully blacklisted refresh token for user {user.email}"
                    )
                except Exception as e:
                    logger.warning(
                        f"API: Could not blacklist specific refresh token for user {user.email}: {str(e)}"
                    )
                    # Continue with account deactivation even if token blacklisting fails

            # Blacklist all outstanding tokens for this user as a safety measure
            try:
                outstanding_tokens = OutstandingToken.objects.filter(user=user)
                for outstanding_token in outstanding_tokens:
                    try:
                        BlacklistedToken.objects.get_or_create(token=outstanding_token)
                    except Exception as e:
                        logger.warning(
                            f"API: Could not blacklist token {outstanding_token.id}: {str(e)}"
                        )
                        continue

                logger.info(
                    f"API: Blacklisted {outstanding_tokens.count()} outstanding tokens for user {user.email}"
                )
            except Exception as e:
                logger.error(
                    f"API: Error blacklisting outstanding tokens for user {user.email}: {str(e)}"
                )
                # Continue with account deactivation even if this fails

            # Deactivate the user account
            user.is_active = False
            user.save(update_fields=["is_active"])

            logger.info(f"API: Successfully deactivated account for user {user.email}")

            return Response(
                {
                    "status": "success",
                    "message": "Account has been successfully deleted. All tokens have been invalidated and the account has been deactivated.",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(
                f"API: Unexpected error during account deletion for user {user.email}: {str(e)}",
                exc_info=True,
            )
            return Response(
                {
                    "status": "error",
                    "message": "An error occurred while deleting the account. Please try again or contact support.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
