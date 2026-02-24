# brain_dump_app/fields.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import base64
import hashlib
import logging

logger = logging.getLogger(__name__)

# Lazy loading for Fernet and KEY to avoid issues during setup/migrations
_CIPHER_SUITE = None
_KEY = None


def get_key():
    global _KEY
    if _KEY is None:
        if not hasattr(settings, "SECRET_KEY") or not settings.SECRET_KEY:
            raise ImproperlyConfigured(
                "SECRET_KEY must be set in Django settings for EncryptedTextField."
            )
        secret_key_bytes = settings.SECRET_KEY.encode("utf-8")
        # Use SHA256 to get a 32-byte hash, then base64 encode for Fernet
        hashed_key = hashlib.sha256(secret_key_bytes).digest()
        _KEY = base64.urlsafe_b64encode(hashed_key)
    return _KEY


def get_cipher_suite():
    global _CIPHER_SUITE
    if _CIPHER_SUITE is None:
        try:
            from cryptography.fernet import Fernet

            _CIPHER_SUITE = Fernet(get_key())
        except ImportError:
            logger.error(
                "Cryptography library is not installed. Please install it to use EncryptedTextField."
            )
            raise ImproperlyConfigured(
                "Cryptography library is not installed. Please install it to use EncryptedTextField."
            )
        except Exception as e:
            logger.error(f"Failed to initialize Fernet cipher: {e}")
            raise ImproperlyConfigured(f"Failed to initialize Fernet cipher: {e}")
    return _CIPHER_SUITE


class EncryptedTextField(models.TextField):
    description = (
        "A TextField that automatically encrypts and decrypts its content using Fernet."
    )

    def get_prep_value(self, value):
        """
        Encrypts the value before saving to the database.
        Value is expected to be a string.
        """
        if value is None:
            return None

        # Ensure value is a string, then encode to bytes for encryption
        if not isinstance(value, str):
            value = str(value)

        value_bytes = value.encode("utf-8")

        try:
            cipher_suite = get_cipher_suite()
            encrypted_data = cipher_suite.encrypt(value_bytes)
            # Store as a string (Fernet output is bytes, so decode to UTF-8)
            return encrypted_data.decode("utf-8")
        except Exception as e:
            logger.error(
                f"Encryption failed for value: {str(value)[:50]}... Error: {e}"
            )
            # Depending on policy, either raise error or return unencrypted
            # For now, let's raise to make issues visible during development
            raise

    def from_db_value(self, value, expression, connection):
        """
        Decrypts the value when loading from the database.
        Value from DB is expected to be a string (the encrypted representation).
        """
        if value is None:
            return None

        # Value from DB should be a string
        if not isinstance(value, str):
            # This case should ideally not happen if get_prep_value stores as str
            logger.warning(
                f"EncryptedTextField received non-string value from DB: {type(value)}"
            )
            value = str(value)

        value_bytes = value.encode("utf-8")

        try:
            from cryptography.fernet import InvalidToken

            cipher_suite = get_cipher_suite()
            decrypted_data = cipher_suite.decrypt(value_bytes)
            return decrypted_data.decode("utf-8")
        except InvalidToken:
            logger.warning(
                f"InvalidToken: Could not decrypt value from DB (value might be unencrypted or corrupted): {value[:50]}..."
            )
            # Return the original value if it cannot be decrypted (e.g., if it was never encrypted)
            return value
        except Exception as e:
            logger.error(
                f"Decryption error for value {value[:50]}...: {e}. Returning raw value."
            )
            # Fallback for other decryption errors
            return value

    def to_python(self, value):
        """
        Converts value to a Python string.
        This is called after from_db_value when loading from DB,
        and also when assigning a value to the field in Python code.
        """
        if isinstance(value, str) or value is None:
            return value
        if isinstance(value, bytes):  # Should ideally be handled by from_db_value
            return value.decode("utf-8")
        return str(value)
