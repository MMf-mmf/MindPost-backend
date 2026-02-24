import logging
import os
import json
from io import BytesIO
from typing import Dict

import httpx
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model

from brain_dump_app.models import BrainDump

# from brain_dump_app.tasks import process_transcription # Assuming you have a task for this

logger = logging.getLogger(__name__)
User = get_user_model()

# WhatsApp API credentials from environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")


@csrf_exempt
def whatsapp_webhook(request):
    """Handles incoming messages and status updates from the WhatsApp Cloud API."""
    if request.method == "GET":
        # Handle webhook verification
        if request.GET.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge"))
        return HttpResponse("Verification token mismatch", status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.debug(f"Received WhatsApp data: {data}")

            change_value = data["entry"][0]["changes"][0]["value"]
            if "messages" in change_value:
                message = change_value["messages"][0]
                from_number = message["from"]

                # Find or create user based on WhatsApp number
                try:
                    user = User.objects.get(phone_number=from_number)
                except User.DoesNotExist:
                    send_response(
                        from_number,
                        "Sorry, your number is not registered. Please sign up first.",
                    )
                    return JsonResponse({"status": "User not found"}, status=403)

                if message["type"] == "audio":
                    audio_content, audio_filename = process_audio_message(message)

                    # Create a BrainDump entry
                    brain_dump = BrainDump.objects.create(
                        user=user,
                        recording=ContentFile(audio_content, name=audio_filename),
                    )
                    # Trigger transcription task (if you have one)
                    # process_transcription.delay(brain_dump.id)

                    send_response(
                        from_number,
                        "Your audio has been received and is being processed.",
                    )

                else:
                    send_response(
                        from_number, "I can only process audio messages at the moment."
                    )

                return JsonResponse({"status": "Message processed"}, status=200)

            elif "statuses" in change_value:
                return JsonResponse({"status": "Status update received"}, status=200)

            else:
                return JsonResponse({"status": "Unknown event type"}, status=400)

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}", exc_info=True)
            return JsonResponse({"status": "Internal server error"}, status=500)

    return HttpResponse("Unsupported method", status=405)


def download_media(media_id: str) -> tuple[bytes, str | None]:
    """Download media from WhatsApp."""
    media_metadata_url = f"https://graph.facebook.com/v21.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    with httpx.Client() as client:
        metadata_response = client.get(media_metadata_url, headers=headers)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        download_url = metadata.get("url")

        media_response = client.get(download_url, headers=headers)
        media_response.raise_for_status()
        return media_response.content, metadata.get("mime_type")


def process_audio_message(message: Dict):
    """Download and prepare audio message."""
    audio_id = message["audio"]["id"]
    audio_content, mime_type = download_media(audio_id)

    # Determine file extension from mime type
    extension = mime_type.split("/")[-1] if mime_type else "mp3"
    filename = f"{audio_id}.{extension}"

    return audio_content, filename


def send_response(from_number: str, response_text: str) -> bool:
    """Send a text response to the user via WhatsApp API."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    json_data = {
        "messaging_product": "whatsapp",
        "to": from_number,
        "type": "text",
        "text": {"body": response_text},
    }

    with httpx.Client() as client:
        response = client.post(
            f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=json_data,
        )

    if response.status_code != 200:
        logger.error(f"Failed to send WhatsApp message: {response.text}")
        return False
    return True
