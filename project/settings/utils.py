import google.auth
from google.cloud import secretmanager
from environs import Env
import os


def get_secret(secret_id, version_id="latest"):
    """
    Get secret from Google Cloud Secret Manager, fall back to .env if local
    """
    try:
        if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:  # Running in GCP/Docker
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/future-nuance-451615-f2/secrets/{secret_id}/versions/{version_id}"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        else:  # Local development
            env = Env()
            env.read_env()
            return env(secret_id)
    except Exception as e:
        raise Exception(f"Error loading secret {secret_id}: {str(e)}")
