#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        print("Error: DJANGO_SETTINGS_MODULE environment variable is not set.")
        print("Please export the correct settings file using the following command:")
        print("export DJANGO_SETTINGS_MODULE=project.settings.local")
        sys.exit(1)

    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
