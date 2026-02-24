import logging, re, uuid, time, os
from django.db import models
from utils.abstract_models import BaseTimestampModel
from django.contrib.auth import get_user_model

# from taggit.managers import TaggableManager
from pgvector.django import VectorField, IvfflatIndex
from django.utils import timezone

# from langchain_text_splitters import RecursiveCharacterTextSplitter

# Import OpenAI libraries
try:
    from openai import OpenAI, APIError

    WHISPER_ENABLED = True
except ImportError:
    WHISPER_ENABLED = False
    logging.warning("openai library not found. Whisper transcription will not work.")

# Assuming utils.abstract_models.BaseTimestampModel provides created_at/updated_at
from utils.abstract_models import BaseTimestampModel
from .fields import EncryptedTextField  # Import the custom field

logger = logging.getLogger("project")
User = get_user_model()


def recording_upload_path(instance, filename):
    """Generate file path for recordings"""
    # Extract original filename without extension and add .mp3
    base_name = os.path.splitext(filename)[0]
    return f"recordings/{instance.user.id}/{base_name}_{uuid.uuid4().hex[:8]}.mp3"


# create a model to hold the recording and its transcription
class BrainDump(BaseTimestampModel):
    """
    Model to hold the recording and its transcription.
    """

    recording = models.FileField(upload_to=recording_upload_path)
    transcription = EncryptedTextField(blank=True)
    edited = models.BooleanField(
        default=False,
        help_text="Whether the transcription has been edited by the user manually.",
    )
    raw_hashtags = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # TODO: Vector embedding field for RAG - typically 1536 dimensions for OpenAI embeddings
    embedding = VectorField(dimensions=1536, null=True)
    # tags = TaggableManager(blank=True)

    class Meta:
        verbose_name = "Brain Dump"
        verbose_name_plural = "Brain Dumps"

        # Add index for faster similarity searches
        indexes = [
            IvfflatIndex(
                name="embedding_ivf_idx",
                fields=["embedding"],
                lists=100,  # Number of partitions, adjust based on your data size
                opclasses=["vector_cosine_ops"],  # Use cosine distance
            )
        ]

    def __str__(self):
        return f"Brain Dump {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    # def extract_hashtags(self):
    #     """Extract hashtags from the transcription"""
    #     if not self.transcription:
    #         return []

    #     # Find all words starting with # in the transcription
    #     hashtags = re.findall(r"#(\w+)", self.transcription.lower())
    #     return hashtags

    # def update_tags_from_transcription(self, save=True):
    #     """Update tags based on hashtags in the transcription"""
    #     hashtags = self.extract_hashtags()

    #     # Store raw hashtags for reference
    #     self.raw_hashtags = " ".join(hashtags)

    #     # Clear existing tags and add new ones
    #     self.tags.clear()
    #     self.tags.add(*hashtags)

    #     if save:
    #         # Save with just the raw_hashtags field to avoid recursion
    #         self.save(update_fields=["raw_hashtags"])

    #     return hashtags

    # def get_related_dumps_by_tags(self, limit=5):
    #     """Find related brain dumps by shared tags"""
    #     from django.db.models import Count

    #     # Get dumps that share tags with this one, ordered by number of shared tags
    #     related = (
    #         BrainDump.objects.filter(tags__in=self.tags.all(), user=self.user)
    #         .exclude(id=self.id)
    #         .annotate(shared_tags=Count("tags"))
    #         .order_by("-shared_tags")[:limit]
    #     )

    #     return related

    """the  commented out code is a proposed implementation for chunking the transcription (when dealing with larger recordings)"""
    # def split_and_generate_embeddings(self, save=True):
    #     """
    #     Splits the transcription into chunks and generates embeddings for each chunk.
    #     Creates and returns ChunkEmbedding objects linked to this BrainDump.
    #     """
    #     if not self.transcription:
    #         return []

    #     # Initialize the text splitter
    #     text_splitter = RecursiveCharacterTextSplitter(
    #         chunk_size=1000,  # Characters per chunk
    #         chunk_overlap=100,  # Overlap between chunks to maintain context
    #         length_function=len,
    #         separators=["\n\n", "\n", ". ", " ", ""]
    #     )

    #     # Split the text
    #     chunks = text_splitter.split_text(self.transcription.strip())

    #     # Initialize OpenAI client
    #     client = OpenAI(api_key=settings.OPENAI_API_KEY)

    #     # Create embedding for each chunk
    #     chunk_embeddings = []
    #     for i, chunk_text in enumerate(chunks):
    #         # Get embedding from OpenAI
    #         response = client.embeddings.create(
    #             input=chunk_text,
    #             model="text-embedding-3-small",
    #         )

    #         # Extract embedding vector
    #         embedding_vector = response.data[0].embedding

    #         # Create ChunkEmbedding object
    #         chunk_embedding = ChunkEmbedding(
    #             brain_dump=self,
    #             chunk_index=i,
    #             chunk_text=chunk_text,
    #             embedding=embedding_vector
    #         )

    #         if save:
    #             chunk_embedding.save()

    #         chunk_embeddings.append(chunk_embedding)

    #     return chunk_embeddings

    # def get_similar_chunks(self, limit=5, query_text=None, query_embedding=None):
    #     """
    #     Returns the most similar chunks across all BrainDumps for this user.

    #     Args:
    #         limit (int): Maximum number of similar chunks to return
    #         query_text (str, optional): Text to search with
    #         query_embedding (list, optional): Directly provide an embedding vector

    #     Returns:
    #         QuerySet: The most similar ChunkEmbeddings
    #     """
    #     # Get query embedding
    #     if query_embedding is None and query_text:
    #         client = OpenAI(api_key=settings.OPENAI_API_KEY)
    #         response = client.embeddings.create(
    #             input=query_text,
    #             model="text-embedding-3-small",
    #         )
    #         query_embedding = response.data[0].embedding
    #     elif query_embedding is None and self.embedding is not None:
    #         query_embedding = self.embedding
    #     else:
    #         return ChunkEmbedding.objects.none()

    #     # Search for similar chunks
    #     similar_chunks = ChunkEmbedding.objects.filter(
    #         brain_dump__user=self.user
    #     ).annotate(
    #         similarity=CosineDistance('embedding', query_embedding)
    #     ).order_by('similarity')[:limit]

    #     return similar_chunks


# class ChunkEmbedding(models.Model):
#     """
#     Stores embeddings for chunks of text from a BrainDump.
#     """
#     brain_dump = models.ForeignKey(BrainDump, on_delete=models.CASCADE, related_name='chunk_embeddings')
#     chunk_index = models.IntegerField()  # The position of this chunk in the original text
#     chunk_text = models.TextField()      # The actual text chunk
#     embedding = VectorField(dimensions=1536, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         indexes = [
#             HnswIndex(
#                 name='hnsw_chunk_embedding_idx',
#                 fields=['embedding'],
#                 m=16,
#                 ef_construction=64,
#                 opclasses=['vector_cosine_ops']
#             )
#         ]


# this model will be a model to store all x/twitter posts
class Post(BaseTimestampModel):
    """
    Model to hold the post and its metadata.
    """

    # post status
    DRAFT = "draft"
    POSTED = "posted"
    POST_STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (POSTED, "Posted"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    brain_dump = models.ManyToManyField(BrainDump, null=True, blank=True)
    post_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    post_type = models.CharField(max_length=255, null=True, blank=True)
    post_url = models.URLField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=POST_STATUS_CHOICES, default=DRAFT)
    content = (
        models.TextField()
    )  # !!Note!! for twitter the max length is 280 characters for free users and Paid subscribers have a 25,000 character limit

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"

    def __str__(self):
        return f"Post {self.post_id} by {self.user.username}"


def post_image_upload_path(instance, filename):
    """Generate file path for post images"""
    return f"post_images/{instance.post.user.id}/{instance.post.id}/{uuid.uuid4().hex[:8]}_{filename}"


class PostImage(BaseTimestampModel):
    """
    Model to store images associated with a Post.
    """

    post = models.ForeignKey(Post, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=post_image_upload_path)
    # Optional: Add fields like caption, order, etc. if needed later

    class Meta:
        verbose_name = "Post Image"
        verbose_name_plural = "Post Images"
        ordering = ["created_at"]  # Default ordering for images within a post

    def __str__(self):
        return f"Image for Post {self.post.id} ({os.path.basename(self.image.name)})"


class TwitterConnection(models.Model):
    """
    Store Twitter OAuth tokens for a user.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="twitter_connection",
    )
    # OAuth 2.0 fields
    oauth2_access_token = EncryptedTextField(blank=True, null=True)
    expires_in = models.IntegerField(
        blank=True, null=True, help_text="Access token expiration time in seconds"
    )
    oauth2_refresh_token = EncryptedTextField(blank=True, null=True)
    expires_at = models.FloatField(
        blank=True, null=True, help_text="Timestamp when the refresh token expires"
    )
    # OAuth 1.0a fields
    oauth1_access_token = EncryptedTextField(blank=True, null=True)
    oauth1_access_token_secret = EncryptedTextField(blank=True, null=True)

    token_type = models.CharField(max_length=50, blank=True, null=True)
    scope = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )  # Store as comma-separated values
    twitter_user_id = models.CharField(max_length=50, blank=True, null=True)
    twitter_username = models.CharField(max_length=50, blank=True, null=True)
    twitter_name = models.CharField(max_length=100, blank=True, null=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    verified = models.BooleanField(
        default=False, help_text="Whether the account is verified on twitter"
    )
    char_limit = models.IntegerField(
        default=280,
        help_text="Character limit for the user. 280 for free users, 25000 for paid subscribers",
    )

    def __str__(self):
        return f"{self.user.email} - @{self.twitter_username}"

    @property
    def is_refresh_valid(self):
        """Check if the refresh token is valid and hasn't expired."""
        if not self.oauth2_refresh_token or not self.expires_at:
            return False

        # Check if token has expired using the expires_at timestamp
        current_time = time.time()
        return current_time < self.expires_at

    @property
    def is_access_valid(self):
        """Check if the access token is valid and hasn't expired."""
        if not self.oauth2_access_token or not self.last_updated or not self.expires_in:
            return False

        try:
            # Calculate when the access token expires:
            # last_updated (as timestamp) + expires_in (duration in seconds)
            last_updated_timestamp = self.last_updated.timestamp()
            access_token_expiry = last_updated_timestamp + self.expires_in

            # Check if current time exceeds expiry
            current_time = time.time()
            return current_time < access_token_expiry
        except (AttributeError, TypeError) as e:
            # Log the error and return False if there's any issue with timestamp calculation
            logger.error(f"Error calculating token expiry: {e}")
            return False


class OAuthState(models.Model):
    """Model for storing OAuth state and PKCE verifiers"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state = models.CharField(max_length=64, unique=True, db_index=True)
    code_verifier = models.CharField(max_length=255)
    redirect_uri = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"OAuth State for {self.user.username} ({self.state})"

    @property
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
