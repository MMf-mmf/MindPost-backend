import io, logging
import os
import json
from pathlib import Path
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.api_core.exceptions import NotFound  # Correct import for NotFound
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv  # To load .env file variables into environment

from .base import *

logging = logging.getLogger("project")
# Determine BASE_DIR if not already defined (might be in base.py)
# Assuming BASE_DIR is defined in base.py or needs to be defined here
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEBUG = False


# --- Helper function to fetch secrets from Google Cloud Secret Manager ---
def fetch_secret(client, secret_id, project_id, version="latest"):
    """Fetches a secret from Google Cloud Secret Manager."""
    secret_name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    logging.info(f"Attempting to fetch secret: {secret_name}")
    try:
        response = client.access_secret_version(request={"name": secret_name})
        return response.payload.data.decode("UTF-8")
    except NotFound:
        logging.warning(f"Warning: Secret {secret_name} not found.")
        return None
    except Exception as e:
        logging.error(f"Error fetching secret {secret_name}: {e}")
        # Optionally, re-raise or raise a custom exception
        # raise ImproperlyConfigured(f"Could not load secret {secret_name}: {e}")
        return None


# --- Load environment variables and GCS credentials from Secret Manager ---
GS_PROJECT_ID = os.getenv("GS_PROJECT_ID")
GS_CREDENTIALS = None

if GS_PROJECT_ID:
    try:
        sm_client = secretmanager.SecretManagerServiceClient()

        # Fetch and load .env content
        env_secret_id = "brain-dump-prod-gcs"
        env_content = fetch_secret(sm_client, env_secret_id, GS_PROJECT_ID)
        if env_content:
            env_file = io.StringIO(env_content)
            load_dotenv(stream=env_file, override=True)
            print(
                f".env variables loaded from Secret Manager (secret: {env_secret_id})."
            )
        else:
            print(
                f"Skipping loading .env from Secret Manager as secret {env_secret_id} was not found or failed to load."
            )

        # Fetch and load GCS credentials
        gcs_creds_secret_id = "brain-dump-gcs-credentials"
        gcs_creds_content = fetch_secret(sm_client, gcs_creds_secret_id, GS_PROJECT_ID)
        if gcs_creds_content:
            credentials_info = json.loads(gcs_creds_content)
            GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
                credentials_info
            )
            print(
                f"GCS credentials loaded from Secret Manager (secret: {gcs_creds_secret_id})."
            )
            DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
            # GS_BUCKET_NAME should be loaded from the .env file fetched earlier
            # This assumes GS_BUCKET_NAME_PRODUCTION is set in the .env content from "brain-dump-prod-gcs"
            GS_BUCKET_NAME = env("GS_BUCKET_NAME_PRODUCTION")
        else:
            print(
                f"GCS credentials secret {gcs_creds_secret_id} not found or failed to load. GCS functionality may be impaired."
            )
            DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

    except Exception as e:
        # This catches errors from SecretManagerServiceClient() or other unexpected issues
        print(f"A critical error occurred during Secret Manager setup: {e}")
        raise ImproperlyConfigured(
            f"Could not initialize settings from Secret Manager: {e}"
        )
else:
    # Local development settings (when GS_PROJECT_ID is not set)
    print("GS_PROJECT_ID not set. Assuming local development environment.")
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    creds_path = BASE_DIR / "creds.json"
    if creds_path.exists():
        GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
            creds_path
        )
        print("GCS credentials loaded from local creds.json file.")
    else:
        print(
            "Warning: creds.json not found locally. GCS functionality may be limited."
        )
# --- End loading environment variables and GCS credentials ---


# Set these to True to use HTTPS in development
SECURE_SSL_REDIRECT = False  # Keep this False for local dev to avoid redirect loops
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"  # Less strict than 'Strict', allows redirects
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Database-backed sessions
SESSION_COOKIE_AGE = 86400  # 1 day in seconds

ALLOWED_HOSTS = [
    "<your-cloud-run-url>.run.app",
    "<your-domain>.com",
]
# the email must be a verified with sendgrid for it to work

CSRF_TRUSTED_ORIGINS = [
    "https://<your-cloud-run-url>.run.app",
    "https://<your-domain>.com",
]
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True  # Only send cookies over HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript from accessing cookies
SESSION_COOKIE_SAMESITE = "Lax"  # Control cross-site request behavior
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Session ends when browser closes
SESSION_COOKIE_AGE = 3600  # Session timeout in seconds (1 hour)

# For CSRF protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Override the bucket name for local development
GS_BUCKET_NAME = env("GS_BUCKET_NAME_PRODUCTION")
SECRET_KEY = env("DJANGO_SECRET_KEY")

SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]

INSTALLED_APPS = THIRD_PARTY_APPS + DJANGO_APPS + LOCAL_APPS

OPENAI_API_KEY = env("OPENAI_API_KEY")
MAIL_GUN_API_KEY = env("MAIL_GUN_API_KEY")
# REDIS_HOST = env("REDIS_HOST")

# Check if the environment variables are set
if not SECRET_KEY or not MAIL_GUN_API_KEY:
    raise ValueError("Please set all the required environment variables.")

ANYMAIL = {
    "MAILGUN_API_KEY": MAIL_GUN_API_KEY,
    # "MAILGUN_SENDER_DOMAIN": "sandbox845a9e9e62a74900b337f34fe506fa41.mailgun.org",
    "MAILGUN_SENDER_DOMAIN": "mindpost.site",
}


# not needed right now
# NPM_BIN_PATH = "/Users/user/.nvm/versions/node/v20.1.0/bin/node"

# INTERNAL_IPS = [
#     "127.0.0.1",
# ]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # AxesMiddleware should be the last middleware in the MIDDLEWARE list.
    # It only formats user lockout messages and renders Axes lockout responses
    # on failed user authentication attempts from login views.
    # If you do not want Axes to override the authentication response
    # you can skip installing the middleware and use your own views.
    # "axes.middleware.AxesMiddleware",
]

# Database configuration


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("PRODUCTION_DATABASE_NAME"),
        "USER": env("PRODUCTION_DATABASE_USER"),
        "PASSWORD": env("PRODUCTION_DATABASE_PASSWORD"),
        "HOST": env("PRODUCTION_DATABASE_HOST"),
        "PORT": "5432",
    }
}


# Redis configuration
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": env("REDIS_URL"),
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#     },
#     "select2": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": env("REDIS_URL"),
#         "TIMEOUT": 600,
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#             "DB": 1,  # Use a different Redis DB
#         },
#     },
# }
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    },
    "select2": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "select2",
        "TIMEOUT": 600,
    },
}
# Optionally set session engine to use Redis
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
# Set the cache backend to select2
SELECT2_CACHE_BACKEND = "select2"


# Stripe Configuration
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY_PRODUCTION", default=None)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY_PRODUCTION", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET_PRODUCTION", default=None)
STRIPE_BASIC_PRICE_ID = env("PRODUCTION_BASIC_PRICE_ID", default=None)
STRIPE_PRO_PRICE_ID = env("PRODUCTION_PRO_PRICE_ID", default=None)


# Twitter API v2 OAuth 2.0 credentials
TWITTER_CLIENT_ID = env("PRODUCTION_CLIENT_ID")
TWITTER_CLIENT_SECRET = env("PRODUCTION_CLIENT_SECRET")

# Legacy Twitter API v1.1 credentials (as fallback) FOR app level (!ONLY!) authentication (this will only authenticate for this app and not any customers)
TWITTER_API_KEY = env("PRODUCTION_API_KEY")
TWITTER_API_SECRET = env("PRODUCTION_API_KEY_SECRET")
TWITTER_ACCESS_TOKEN = env("PRODUCTION_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = env("PRODUCTION_ACCESS_SECRET")

DEV_PHONE_NUMBER = env("DEV_PHONE_NUMBER")
# X_API_KEY_BEARER_KEY = env("X_API_KEY_BEARER_KEY")

SITE_ID = 1

# The GCS and .env loading logic has been moved to the top of the file.
# GS_BUCKET_NAME is now set within the new consolidated block if GS_PROJECT_ID is defined.
# DEFAULT_FILE_STORAGE is also set conditionally within that block.
# GS_CREDENTIALS is also set conditionally within that block.
