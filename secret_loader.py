import os

from google.cloud import secretmanager


def get_secret(secret_id: str, project_id: str | None = None) -> str:
    """Fetch the latest version of a secret from GCP Secret Manager.

    Args:
        secret_id: The name of the secret (e.g. 'google-maps-api-key').
        project_id: GCP project ID. Defaults to the GOOGLE_CLOUD_PROJECT env var.

    Returns:
        The secret value as a UTF-8 string.
    """
    if project_id is None:
        project_id = os.environ["GOOGLE_CLOUD_PROJECT"]

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def load_secrets() -> None:
    """Fetch secrets from GCP Secret Manager and inject them into the environment.

    Uses setdefault so that any value already present in the environment
    (e.g. set manually for local testing) is not overwritten.  Each secret
    is fetched independently so a single missing secret does not prevent the
    others from loading.
    """
    _secrets = {
        "GOOGLE_MAPS_API_KEY": "google-maps-api-key",
        "FOOTBALL_DATA_API_KEY": "football-data-key",
    }
    for env_var, secret_id in _secrets.items():
        try:
            os.environ.setdefault(env_var, get_secret(secret_id))
        except Exception:
            pass
