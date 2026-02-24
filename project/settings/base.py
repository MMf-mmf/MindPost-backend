from pathlib import Path
import os
from environs import Env
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

env = Env()
env.read_env()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent


# Application definition

# Authentication URLs
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "brain_dump_list"
LOGOUT_REDIRECT_URL = "login"


DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.sites", # not needed, as of first writing
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "anymail",  # for sending emails
    "django_select2",
    "django_recaptcha",
    # UNFOLD:
    "unfold",  # before django.contrib.admin
    "unfold.contrib.filters",  # optional, if special filters are needed
    "unfold.contrib.forms",  # optional, if special form elements are needed
    "unfold.contrib.inlines",  # optional, if special inlines are needed
    "unfold.contrib.import_export",  # optional, if django-import-export package is used
    # "unfold.contrib.guardian",  # optional, if django-guardian package is used
    "unfold.contrib.simple_history",  # optional, if django-simple-history package is used
    "import_export",
    # "easy_thumbnails",
    # "filer",
    # "axes",
    "taggit",
    # Added for API support
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "mathfilters",
    # PACKAGES I SEE US NEEDING IN THE FUTURE
    # "storages",  # for storing files on AWS OR OTHER EXTERNAL STORAGE
    # "rest_framework.authtoken",
    # "allauth",  # for user authentication
    # "allauth.account",  # for user authentication
    # "allauth.socialaccount",
    # "django_htmx",
    # "widget_tweaks",  # for form customization
    # "mathfilters",  # for math operations in templates
    # "django_countries",  # for country fields
    # "phonenumber_field",
]

LOCAL_APPS = [
    "users_app",
    "brain_dump_app",
    "subscriptions_app",
    "whatsapp_app",
]


TAILWIND_CSS_PATH = "css/dist/styles.css"
THUMBNAIL_PROCESSORS = (
    "easy_thumbnails.processors.colorspace",
    "easy_thumbnails.processors.autocrop",
    #'easy_thumbnails.processors.scale_and_crop',
    "filer.thumbnail_processors.scale_and_crop_with_subject_location",
    "easy_thumbnails.processors.filters",
)
# if we start using subdomains below should be uncommented as well as the subdomains package should be installed,
# ROOT_HOSTCONF = "project.hosts"
# DEFAULT_HOST = "main_site_urls"
ROOT_URLCONF = "project.urls"
AUTH_USER_MODEL = "users_app.CustomUser"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"


AUTHENTICATION_BACKENDS = (
    # "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    # "utils.permissions.PropertyBasedPermissionBackend",  # Custom property-based permissions
    # "allauth.account.auth_backends.AuthenticationBackend",
)

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

# TIME_ZONE = 'UTC'
TIME_ZONE = "America/Chicago"


USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
# # Base url to serve media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
    os.path.join(BASE_DIR, "node_modules"),
]

# File Upload Settings
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755


# GS_BUCKET_NAME = env("GS_BUCKET_NAME")  # Required in all environments


GS_QUERYSTRING_AUTH = True
GS_FILE_OVERWRITE = False
GS_MAX_MEMORY_SIZE = 5242880  # 5MB
# Remove GS_DEFAULT_ACL since bucket uses uniform bucket-level access

# Default storage configuration uses Google Cloud Storage
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


DEFAULT_FROM_EMAIL = "noreply@mindpost.site"


# django-allauth settings
# LOGIN_REDIRECT_URL = "home"
# ACCOUNT_LOGOUT_REDIRECT = "home"
# ACCOUNT_SIGNUP_REDIRECT_URL = "home"  # '/accounts/email/'
# # this will remove the remember me checkbox on the login page, and just remember the user
# ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# ACCOUNT_EMAIL_REQUIRED = True
# ACCOUNT_USERNAME_REQUIRED = False
# ACCOUNT_AUTHENTICATION_METHOD = "email"
# ACCOUNT_SESSION_REMEMBER = True
# ACCOUNT_UNIQUE_EMAIL = True
# ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
# ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# ACCOUNT_LOGIN_BY_CODE_ENABLED = True
# ACCOUNT_EMAIL_NOTIFICATIONS = True
# ACCOUNT_CHANGE_EMAIL = True

# ACCOUNT_FORMS = {
#     "login": "accounts_app.forms.CustomLoginForm",
# }
"""EMAIL CONFIGURATION"""

EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

# CELERY_IMPORTS = ("utils.email_sender",)

# TEXT SETTINGS
# TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID')
# TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN')
# TWILIO_PHONE_NUMBER = env('TWILIO_DEFAULT_CALLERID')


# ENTRYPOINT FOR THE ASGI SERVER
# ASGI_APPLICATION = "project.asgi.application"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "50/day", "user": "1000/day"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Simple JWT settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env(
        "SECRET_KEY",
        default="xxt*django-insecure-default-key-for-jwt-...888replace-thisxx",
    ),
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}


ADMINS = [
    ("Admin", "admin@example.com"),
]

# LOGGING
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "email": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
            "filters": ["require_debug_false"],
        },
        # 'file': {
        #     'level': 'DEBUG',
        #     'class': 'logging.FileHandler',
        #     'filename': '/path/to/log/file.log',
        #     'formatter': 'verbose',
        # },
    },
    "loggers": {
        # 'django': {
        #     'handlers': ['console', 'email'],
        #     'level': 'INFO',
        # },
        "project": {
            "handlers": ["console", "email"],
            "level": "DEBUG",
        },
    },
}
# TODO: WHEN SET UP REDIS PROPERLY, UNCOMMENT THIS THE REDIS CONFIGURATION
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
#         "LOCATION": "default-cache",
#     },
#     "select2": {
#         "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
#         "LOCATION": "select2-cache",
#         "TIMEOUT": 600,  # Set timeout to 10 minutes
#     },
# }

# CELERY_BROKER_URL = "redis://localhost:6379/0"
# CELERY_RESULT_BACKEND = "redis://localhost:6379/0"


# recaptcha settings
# RECAPTCHA_PUBLIC_KEY = os.environ.get("RECAPTCHA_PUBLIC_KEY")
# RECAPTCHA_PRIVATE_KEY = os.environ.get("RECAPTCHA_PRIVATE_KEY")
# RECAPTCHA_REQUIRED_SCORE = 0.85


# TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
# TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
# TWILIO_PHONE_NUMBER = env("TWILIO_PHONE_NUMBER")
# YOUR_PHONE_NUMBER = env("DEV_PHONE_NUMBER")


CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    # Add your mobile app domains/IPs here
]


# SUBSCRIPTION RATE LIMITINGS
BASIC_USER = {
    "max_recording": 20,
    "max_recording_length": 5,  # in minutes
    "max_post_generations": 30,
    "max_post_submissions": 10,
    "max_chat_messages": 50,
}

PRO_USER = {
    "max_recording": 50,
    "max_recording_length": 10,  # in minutes
    "max_post_generations": 60,
    "max_post_submissions": 20,
    "max_chat_messages": 100,
}


X_POST_LIMIT_FREE = 280
X_POST_LIMIT_PRO = 25_000
