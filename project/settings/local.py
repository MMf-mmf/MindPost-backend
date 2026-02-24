from .base import *
import os, json
from google.oauth2 import service_account
from google.cloud import secretmanager
from django.core.exceptions import ImproperlyConfigured

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Set these to True to use HTTPS in development
SECURE_SSL_REDIRECT = False  # Keep this False for local dev to avoid redirect loops
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"  # Less strict than 'Strict', allows redirects
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Database-backed sessions
SESSION_COOKIE_AGE = 86400  # 1 day in seconds

ALLOWED_HOSTS = ["*"]
# the email must be a verified with sendgrid for it to work
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
# Update CORS settings for mobile app
# ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1", "10.175.88.155"]
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:8000",
#     "http://localhost:3000",
#     "http://0.0.0.0:8000",
#     # Add your mobile app domains/IPs here
# ]


# Override the bucket name for local development
GS_BUCKET_NAME = env("GS_BUCKET_NAME_STAGING")

SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]

THIRD_PARTY_APPS += [
    "debug_toolbar",
    "django_extensions",
]
INSTALLED_APPS = THIRD_PARTY_APPS + DJANGO_APPS + LOCAL_APPS


SECRET_KEY = env("DJANGO_SECRET_KEY")
MAIL_GUN_API_KEY = env("MAIL_GUN_API_KEY")
OPENAI_API_KEY = env("OPENAI_API_KEY")
# REDIS_HOST = env("REDIS_HOST")

# Check if the environment variables are set
if not SECRET_KEY or not MAIL_GUN_API_KEY:
    raise ValueError("Please set all the required environment variables.")

ANYMAIL = {
    "MAILGUN_API_KEY": MAIL_GUN_API_KEY,
    # "MAILGUN_SENDER_DOMAIN": "sandbox845a9e9e62a74900b337f34fe506fa41.mailgun.org",
    "MAILGUN_SENDER_DOMAIN": "mindpost.site",  # this is when there is a paid account
}


# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [(REDIS_HOST, env.int("REDIS_PORT"))],
#         },
#     },
# }
# test the redis connection
# import redis

# try:
#     redis_client = redis.StrictRedis(host=REDIS_HOST, port=env.int("REDIS_PORT"), db=0)
#     redis_client.ping()
# except redis.ConnectionError:
#     print("Could not connect to Redis.")


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
]

# LOCAL DATABASE CONNECTED TO SQLITE (NOT CURRENTLY USED)
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

# CONNECTED TO Local DATABASE
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": env("LOCAL_DATABASE_NAME"),
#         "USER": env("LOCAL_DATABASE_USER"),
#         "PASSWORD": env("LOCAL_DATABASE_PASSWORD"),
#         "HOST": env("LOCAL_DATABASE_HOST", default="localhost"),
#         "PORT": env.int("LOCAL_DATABASE_PORT", default=5432),
#     }
# }

# STAGING DATABASE
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": env("DEVELOPMENT_DATABASE_NAME"),
#         "USER": env("DEVELOPMENT_DATABASE_USER"),
#         "PASSWORD": env("DEVELOPMENT_DATABASE_PASSWORD"),
#         "HOST": env("DEVELOPMENT_DATABASE_HOST", default="localhost"),
#         "PORT": env.int("DEVELOPMENT_DATABASE_PORT", default=5432),
#     }
# }

# PRODUCTION DATABASE
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

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    # 'debug_toolbar.panels.history.HistoryPanel',
    # 'debug_toolbar.panels.versions.VersionsPanel',
    # 'debug_toolbar.panels.timer.TimerPanel',
    # 'debug_toolbar.panels.settings.SettingsPanel',
    # 'debug_toolbar.panels.headers.HeadersPanel',
    # 'debug_toolbar.panels.signals.SignalsPanel',
    # 'debug_toolbar.panels.redirects.RedirectsPanel',
    # 'debug_toolbar.panels.profiling.ProfilingPanel',
]

# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/1",
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#     },
#     "select2": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/2",  # Use a different Redis database for select2 cache
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#         "TIMEOUT": 600,  # Set timeout to 10 minutes
#     },
#     "celery": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/0",
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#     },
# }
# SESSION_CACHE_ALIAS = "default"
# # Set the cache backend to select2
# SELECT2_CACHE_BACKEND = "select2"
# Replace the Redis cache configuration with a local memory cache
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

# Use database sessions instead of Redis
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# SESSION_CACHE_ALIAS = "default"  # Not needed with db sessions

# Set the cache backend to select2
SELECT2_CACHE_BACKEND = "select2"
SITE_ID = 1


# Stripe Configuration (using staging keys for local dev)
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY_STAGING", default=None)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY_STAGING", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET_STAGING", default=None)
STRIPE_BASIC_PRICE_ID = env("STAGING_BASIC_PRICE_ID", default=None)
STRIPE_PRO_PRICE_ID = env("STAGING_PRO_PRICE_ID", default=None)


# Twitter API v2 OAuth 2.0 credentials
TWITTER_CLIENT_ID = env("LOCAL_X_2_0_CLIENT_ID")
TWITTER_CLIENT_SECRET = env("LOCAL_X_2_0_CLIENT_SECRET")
# Legacy Twitter API v1.1 credentials (as fallback) FOR app level (!ONLY!) authentication (this will only authenticate for this app and not any customers)
TWITTER_API_KEY = env("LOCAL_CONSUMER_API_KEY")
TWITTER_API_SECRET = env("LOCAL_CONSUMER_API_KEY_SECRET")
TWITTER_ACCESS_TOKEN = env("LOCAL_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = env("LOCAL_ACCESS_SECRET")
# X_API_KEY_BEARER_KEY = env("X_API_KEY_BEARER_KEY")
DEV_PHONE_NUMBER = env("DEV_PHONE_NUMBER")
GS_PROJECT_ID = env("GS_PROJECT_ID")
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
