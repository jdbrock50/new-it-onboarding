
"""Read-only access to Shore's Google Workspace user directory."""

from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

GOOGLE_DOMAIN = "shorecollaborative.org"
DELEGATED_ADMIN = "jmercado@shorecollaborative.org"

SCOPES = (
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = (
    PROJECT_ROOT / "credentials" / "shore-service-account.json"
)


def create_directory_service():
    """Create an authenticated, read-only Directory API service."""
    if not CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(
            "Google Workspace service-account credentials were not found."
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
    )

    delegated_credentials = credentials.with_subject(DELEGATED_ADMIN)

    return build(
        "admin",
        "directory_v1",
        credentials=delegated_credentials,
        cache_discovery=False,
    )


def get_workspace_usernames() -> set[str]:
    """Retrieve usernames and aliases across all directory pages.

    Raises an exception if any request fails, preventing callers from
    treating an incomplete lookup as proof of username availability.
    """
    service = create_directory_service()
    usernames: set[str] = set()
    page_token = None
    suffix = f"@{GOOGLE_DOMAIN}"

    while True:
        response = (
            service.users()
            .list(
                domain=GOOGLE_DOMAIN,
                maxResults=500,
                pageToken=page_token,
                fields="nextPageToken,users(primaryEmail,aliases,nonEditableAliases)",
            )
            .execute()
        )

        for user in response.get("users", []):
            addresses = [
                user.get("primaryEmail", ""),
                *(user.get("aliases") or []),
                *(user.get("nonEditableAliases") or []),
            ]

            for address in addresses:
                normalized_address = address.strip().lower()

                if normalized_address.endswith(suffix):
                    username = normalized_address[: -len(suffix)]
                    if username:
                        usernames.add(username)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return usernames


def test_google_workspace_connection() -> bool:
    """Test directory access without displaying account information."""
    try:
        usernames = get_workspace_usernames()

        print("Google Workspace connection successful.")
        print("Directory API access: READ ONLY")
        print(f"Domain: {GOOGLE_DOMAIN}")
        print(f"Delegated account: {DELEGATED_ADMIN}")
        print(f"Reserved user addresses found: {len(usernames)}")
        return True

    except FileNotFoundError:
        print("ERROR: Service-account credentials file was not found.")
        return False

    except HttpError as exc:
        status = getattr(exc.resp, "status", "unknown")
        print(f"Google Workspace API error (HTTP {status}).")
        return False

    except (OSError, ValueError) as exc:
        print(f"Credential configuration error: {type(exc).__name__}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if test_google_workspace_connection() else 1)
