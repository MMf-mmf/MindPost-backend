from .models import BrainDump
import logging, json
import tempfile, os
from django.conf import settings
from pgvector.django import CosineDistance
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from rest_framework import status
from utils.prompts import (
    TWITTER_PROMPT_SHORT,
    TWITTER_PROMPT_MEDIUM,
    TWITTER_PROMPT_LONG,
)

# Import OpenAI libraries
try:
    from openai import OpenAI, APIError

    WHISPER_ENABLED = True
except ImportError:
    WHISPER_ENABLED = False
    logging.warning("openai library not found. Whisper transcription will not work.")

logger = logging.getLogger("project")


def transcribe_audio_file(audio_file):
    """
    Transcribe an audio file using OpenAI Whisper API.

    Args:
        audio_file: InMemoryUploadedFile from the request

    Returns:
        str: Transcription text or empty string if failed
    """
    # Check if Whisper is available
    if not WHISPER_ENABLED:
        logger.error("OpenAI library not available. Cannot transcribe.")
        return ""

    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Get the real file extension from the content type if available
        content_type = (
            audio_file.content_type if hasattr(audio_file, "content_type") else None
        )

        # Map content types to extensions
        content_type_map = {
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".mp4",
            "audio/m4a": ".m4a",
            "audio/wav": ".wav",
            "audio/wave": ".wav",
            "audio/x-wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
        }

        # Use the original file extension as default, or .mp3 if we can't determine
        extension = "." + audio_file.name.split(".")[-1].lower()
        if content_type and content_type in content_type_map:
            extension = content_type_map[content_type]

        # Create a temporary file with the proper extension
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
            temp_path = temp_file.name

            # Reset the file pointer to the beginning
            audio_file.seek(0)

            # Write the uploaded file to the temp file
            for chunk in audio_file.chunks():
                temp_file.write(chunk)

            # Close the file to ensure all data is written
            temp_file.flush()

        try:
            # Remove breakpoint that was causing execution to pause
            # Open the temporary file for reading
            with open(temp_path, "rb") as audio_data:
                # Call OpenAI Whisper API
                transcript_response = client.audio.transcriptions.create(
                    model="whisper-1", file=audio_data, response_format="text"
                )

                # Return the transcription
                if transcript_response:
                    logger.info("Whisper transcription successful")
                    return transcript_response
                else:
                    return ""

        except APIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            return ""
        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            return ""
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        logger.error(
            f"Unhandled exception in transcription process: {e}", exc_info=True
        )
        return ""


def generate_embedding(dump_id=None, transcription=None):
    """
    Generate vector embedding for the transcription text
    using OpenAI's embedding API.
    """
    # Handle case when only transcription is provided
    if transcription and not dump_id:
        if not settings.OPENAI_API_KEY:
            return None

        try:
            # Initialize OpenAI client
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Get embedding from OpenAI
            response = client.embeddings.create(
                input=transcription.strip(),
                model="text-embedding-3-small",  # Use text-embedding-3-large for more accuracy
            )

            # Extract embedding vector
            embedding_vector = response.data[0].embedding
            logger.info("Generated embedding for provided transcription")
            return embedding_vector

        except APIError as e:
            logger.error(f"OpenAI API error generating embedding: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            return None

    # Original flow for when dump_id is provided
    try:
        brain_dump = BrainDump.objects.get(id=dump_id)
    except BrainDump.DoesNotExist:
        logger.error(f"BrainDump with id {dump_id} does not exist.")
        return None
    except Exception as e:
        logger.error(f"Error retrieving BrainDump: {e}", exc_info=True)
        return None
    if not brain_dump.transcription or not settings.OPENAI_API_KEY:
        return None

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Get embedding from OpenAI
        response = client.embeddings.create(
            input=brain_dump.transcription.strip(),
            model="text-embedding-3-small",  # Use text-embedding-3-large for more accuracy
        )

        # Extract embedding vector
        embedding_vector = response.data[0].embedding

        # Store in the model
        brain_dump.embedding = embedding_vector
        brain_dump.save(update_fields=["embedding"])

        logger.info(f"Generated embedding for BrainDump {brain_dump.id}")
        return embedding_vector

    except APIError as e:
        logger.error(f"OpenAI API error generating embedding: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error generating embedding: {e}", exc_info=True)
        return None


def get_similar_dumps(dump_object, query_text=None, limit=5, exclude_self=True):
    """
    Returns the most similar BrainDumps to this one based on embedding similarity.
    Can also find dumps similar to a provided text query.

    Args:
        limit (int): The maximum number of similar dumps to return
        exclude_self (bool): Whether to exclude the current dump from results
        query_text (str, optional): Text to search with instead of this dump's embedding

    Returns:
        QuerySet: The most similar BrainDumps
    """
    # If query_text is provided, generate an embedding for it
    if query_text:
        query_embedding = generate_embedding(dump_id=None, transcription=query_text)
    else:
        # Otherwise use this dump's embedding
        if dump_object.embedding is None:
            return BrainDump.objects.none()
        query_embedding = dump_object.embedding

    # Get similar dumps by cosine similarity
    # Lower value means more similar for cosine distance
    similar_dumps = (
        BrainDump.objects.filter(
            user=dump_object.user,  # Only get dumps from the same user
            embedding__isnull=False,  # Ensure we only compare with dumps that have embeddings
        )
        .annotate(similarity=CosineDistance("embedding", query_embedding))
        .order_by("similarity")
    )

    # Exclude dump_object if requested (only if we're not using a text query)
    if exclude_self and not query_text:
        similar_dumps = similar_dumps.exclude(id=dump_object.id)

    return similar_dumps[:limit]


def generate_post(brain_dumps, post_type="twitter", min_chars=0, max_chars=280):
    min_chars = int(min_chars)
    max_chars = int(max_chars)
    """
    Generate a post based on the provided brain dumps using LangChain.
    Returns posts in JSON format for easier processing.

    Args:
        brain_dumps: QuerySet of BrainDump objects
        post_type: Type of post to generate (twitter, blog, etc.)
        min_chars: Minimum character length for the post (default is 0)
        max_chars: Maximum character length for the post (default is 280 for Twitter)

    Returns:
        str: JSON string containing generated post content(s)
    """
    try:
        # Collect all transcriptions
        transcriptions = [
            dump.transcription for dump in brain_dumps if dump.transcription
        ]

        if not transcriptions:
            return json.dumps({"error": "No content available to generate post."})

        # Join transcriptions with separators for clarity
        all_thoughts = "\n---\n".join(transcriptions)

        # Configure the model
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0,
            max_tokens=2000,  # Set a limit to prevent unexpected long outputs
            timeout=30,  # Set a timeout to avoid hanging requests
            max_retries=1,  # Allow retries for transient errors
        )

        # Select prompt template based on post type and max_chars
        if post_type == "twitter":
            if max_chars <= 280:
                template = TWITTER_PROMPT_SHORT
            elif max_chars <= 1000:
                template = TWITTER_PROMPT_MEDIUM
            else:  # max_chars > 1000
                template = TWITTER_PROMPT_LONG

            # TODO: Add logic for other post_types like 'blog' if needed
            prompt = ChatPromptTemplate.from_template(template)

        else:
            # Handle unsupported post types directly
            logger.warning(f"Unsupported post_type: {post_type}.")
            return json.dumps(
                {"error": f"Post generation for type '{post_type}' is not supported."}
            )
            # If you wanted a default prompt instead of an error:
            # logger.warning(f"Unsupported post_type: {post_type}. Using default prompt.")
            # default_template = "Generate content based on these thoughts: {thoughts}"
            # prompt = ChatPromptTemplate.from_template(default_template)

        # Generate the post(s)
        chain = prompt | llm
        result = chain.invoke(
            {"thoughts": all_thoughts, "min_chars": min_chars, "max_chars": max_chars}
        )

        # Extract the content from the response, ensuring it's a string
        response_content = result.content
        if isinstance(response_content, str):
            response_content = response_content.strip()
        else:
            # Log unexpected type and handle appropriately
            logger.error(
                f"Unexpected type for result.content in post generation: {type(response_content)}. Content: {response_content}"
            )
            # Fallback: try converting to string, or return error earlier
            response_content = str(response_content).strip()  # Basic fallback

        # Try to parse the response as JSON
        try:
            # Extract JSON if it's wrapped in code blocks
            if "```json" in response_content:
                json_text = response_content.split("```json")[1].split("```")[0].strip()
            else:
                json_text = response_content

            # Validate by parsing
            posts_data = json.loads(json_text)

            # Ensure it's a valid format
            if not isinstance(posts_data, list):
                posts_data = [
                    {
                        "post_text": response_content,
                        "topics": [],
                        "character_count": len(response_content),
                    }
                ]

            logger.info(
                f"Generated {len(posts_data)} posts successfully for user {brain_dumps.first().user.id}"
            )

            return json.dumps(posts_data)

        except json.JSONDecodeError:
            # If parsing fails, return a fallback format
            logger.warning(
                f"Failed to parse LLM response as JSON, using fallback format"
            )
            return json.dumps(
                [
                    {
                        "post_text": response_content,
                        "topics": [],
                        "character_count": len(response_content),
                    }
                ]
            )

    except Exception as e:
        logger.error(f"Error generating post with LangChain: {str(e)}", exc_info=True)
        return json.dumps({"error": "Failed to generate post. Please try again later."})


def generate_chat_response(user, message):
    """
    Helper function to generate chat response based on user's message
    by finding similar brain dumps and creating an LLM response.

    Args:
        user: The user who sent the message
        message: The user's query message

    Returns:
        tuple: (response_text, status_code) or (error_message, status_code)
    """
    # Get any brain dump from the user to use as reference
    user_dump = BrainDump.objects.filter(user=user).first()
    if not user_dump:
        return {"error": "No brain dumps found"}, status.HTTP_404_NOT_FOUND

    # Get similar brain dumps using vector similarity
    similar_dumps = get_similar_dumps(
        dump_object=user_dump, query_text=message, limit=3
    )

    # Extract transcriptions from similar dumps
    context_texts = [dump.transcription for dump in similar_dumps if dump.transcription]
    if not context_texts:
        return {
            "response": "I couldn't find any relevant information in your brain dumps about that topic."
        }, status.HTTP_200_OK

    # Create the chat prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant answering questions based on the user's past brain dumps.
            Use the following context derived from the user's recordings to answer their question accurately.
            If the provided context does not contain enough information to fully answer the question, say so.
            Base your answer only on the provided context, don't make assumptions or add external information.""",
            ),
            (
                "user",
                """Context from brain dumps:
            ---
            {context}
            ---

            Question: {question}

            Answer:""",
            ),
        ]
    )

    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        max_tokens=2000,
        timeout=30,
        max_retries=1,
    )

    # Create and invoke the chain
    chain = prompt | llm
    result = chain.invoke(
        {"context": "\n---\n".join(context_texts), "question": message}
    )

    # Ensure result.content is a string before stripping
    response_text = result.content
    if isinstance(response_text, str):
        response_text = response_text.strip()
    else:
        # Log unexpected type and handle appropriately
        logger.error(
            f"Unexpected type for result.content in chat: {type(response_text)}. Content: {response_text}"
        )
        # Decide on fallback behavior, e.g., return raw content or an error message
        response_text = str(response_text)  # Convert to string as a basic fallback

    return {"response": response_text}, status.HTTP_200_OK
