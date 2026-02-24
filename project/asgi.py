"""
ASGI config for project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from pathlib import Path

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

application = get_asgi_application()
