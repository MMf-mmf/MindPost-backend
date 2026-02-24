from .base import *
import os, json
from google.oauth2 import service_account
from google.cloud import secretmanager
from django.core.exceptions import ImproperlyConfigured

DEBUG = False

# Set these to True to use HTTPS in development
SECURE_SSL_REDIRECT = False  # Keep this False for local dev to avoid redirect loops
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"  # Less strict than 'Strict', allows redirects
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Database-backed sessions
SESSION_COOKIE_AGE = 86400  # 1 day in seconds

ALLOWED_HOSTS = [
    "<your-staging-cloud-run-url>.run.app",
    "staging.<your-domain>.com",
]
# the email must be a verified with sendgrid for it to work

CSRF_TRUSTED_ORIGINS = [
    "https://<your-staging-cloud-run-url>.run.app",
    "https://staging.<your-domain>.com",
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
GS_BUCKET_NAME = env("GS_BUCKET_NAME_STAGING")
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

# Parse the Cloud SQL database URL format:
# postgres://postgres:pass@/cloudsql/project:region:instance/dbname
if not os.getenv("USE_CLOUD_SQL_AUTH_PROXY", None):
    try:
        # db_url = env.str("STAGING_DATABASE_URL")  # Using environs' str() method
        # # Extract components from the URL
        # user = db_url.split("://")[1].split(":")[0]
        # password = env("DEVELOPMENT_DATABASE_PASSWORD")
        # instance_name = db_url.split("/cloudsql/")[1].split("/")[0]
        # database = db_url.split("/")[-1]

        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": env("DEVELOPMENT_DATABASE_NAME"),
                "USER": env("DEVELOPMENT_DATABASE_USER"),
                "PASSWORD": env("DEVELOPMENT_DATABASE_PASSWORD"),
                "HOST": env("STAGING_DATABASE_HOST"),
                "PORT": "5432",
            }
        }
    except (IndexError, ValueError) as e:
        raise ValueError(f"Invalid DATABASE_URL format: {e}")
else:
    # Using Cloud SQL proxy with development settings
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("DEVELOPMENT_DATABASE_NAME"),
            "USER": env.str("DEVELOPMENT_DATABASE_USER"),
            "PASSWORD": env.str("DEVELOPMENT_DATABASE_PASSWORD"),
            "HOST": env("DEVELOPMENT_DATABASE_HOST"),
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
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY_STAGING", default=None)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY_STAGING", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET_STAGING", default=None)
STRIPE_BASIC_PRICE_ID = env("STAGING_BASIC_PRICE_ID", default=None)
STRIPE_PRO_PRICE_ID = env("STAGING_PRO_PRICE_ID", default=None)


# Twitter API v2 OAuth 2.0 credentials
TWITTER_CLIENT_ID = env("STAGING_X_2_0_CLIENT_ID")
TWITTER_CLIENT_SECRET = env("STAGING_X_2_0_CLIENT_SECRET")

# Legacy Twitter API v1.1 credentials (as fallback) FOR app level (!ONLY!) authentication (this will only authenticate for this app and not any customers)
TWITTER_API_KEY = env("STAGING_CONSUMER_API_KEY")
TWITTER_API_SECRET = env("STAGING_CONSUMER_API_KEY_SECRET")
TWITTER_ACCESS_TOKEN = env("STAGING_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = env("STAGING_ACCESS_SECRET")
# X_API_KEY_BEARER_KEY = env("X_API_KEY_BEARER_KEY")
DEV_PHONE_NUMBER = env("DEV_PHONE_NUMBER")
GS_PROJECT_ID = env("GS_PROJECT_ID")
SITE_ID = 1


if os.getenv("GOOGLE_CLOUD_PROJECT"):
    # Cloud Run/GCP environment settings
    DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
    GS_BUCKET_NAME = env("GS_BUCKET_NAME_STAGING")  # Use staging bucket in GCP
    try:
        # Fetch credentials from Secret Manager
        client = secretmanager.SecretManagerServiceClient()
        # IMPORTANT: Replace 'gcs-service-account-key' with the actual name of your secret in GCP Secret Manager
        secret_id = env("GCS_SECRET_NAME", "gcs-service-account-key")
        secret_name = f"projects/{GS_PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": secret_name})
        secret_payload = response.payload.data.decode("UTF-8")
        credentials_info = json.loads(secret_payload)
        GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
            credentials_info
        )
        print("GCS credentials loaded from Secret Manager.")
    except Exception as e:
        # Handle potential errors (e.g., secret not found, permission issues)
        # Log the error and potentially raise a configuration error
        print(f"Error fetching GCS credentials from Secret Manager: {e}")
        # Depending on your error handling strategy, you might want to exit or use default creds
        raise ImproperlyConfigured(
            f"Could not load GCS credentials from Secret Manager: {e}"
        )
else:
    # Local development settings
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    # Optionally set a local bucket name if needed, or leave GS_BUCKET_NAME unset
    # GS_BUCKET_NAME = "your-local-dev-bucket" # Example

    # Local development: Load credentials from file
    creds_path = BASE_DIR / "creds.json"
    if creds_path.exists():
        GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
            creds_path
        )
    else:
        # Handle case where creds.json is missing locally
        print(
            "Warning: creds.json not found for local GCS credentials. GCS functionality may be limited."
        )
        GS_CREDENTIALS = (
            None  # Set to None or handle as appropriate if GCS is optional locally
        )
