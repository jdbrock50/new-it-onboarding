"""Read-only access to Shore's Google Workspace user and group directories."""

from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

GOOGLE_DOMAIN = "shorecollaborative.org"
DELEGATED_ADMIN = "jmercado@shorecollaborative.org"

SCOPES = (
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
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


def _add_domain_addresses(
    usernames: set[str], addresses: list[str],
) -> None:
    """Add local parts of addresses belonging to Shore's domain."""
    suffix = f"@{GOOGLE_DOMAIN}"

    for address in addresses:
        normalized_address = address.strip().lower()
        if normalized_address.endswith(suffix):
            username = normalized_address[: -len(suffix)]
            if username:
                usernames.add(username)


def get_workspace_usernames() -> set[str]:
    """Retrieve user addresses and aliases across all directory pages.

    Raises an exception if any request fails, preventing callers from
    treating an incomplete lookup as proof of username availability.
    """
    service = create_directory_service()
    usernames: set[str] = set()
    page_token = None

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
            _add_domain_addresses(usernames, addresses)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return usernames


def get_workspace_group_usernames() -> set[str]:
    """Retrieve Google Group addresses and aliases across all pages.

    Raises an exception on any failed request so incomplete results are
    never mistaken for a successful collision check.
    """
    service = create_directory_service()
    usernames: set[str] = set()
    page_token = None

    while True:
        response = (
            service.groups()
            .list(
                domain=GOOGLE_DOMAIN,
                maxResults=200,
                pageToken=page_token,
                fields="nextPageToken,groups(email,aliases,nonEditableAliases)",
            )
            .execute()
        )

        for group in response.get("groups", []):
            addresses = [
                group.get("email", ""),
                *(group.get("aliases") or []),
                *(group.get("nonEditableAliases") or []),
            ]
            _add_domain_addresses(usernames, addresses)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return usernames


def test_google_workspace_connection() -> bool:
    """Test user and group directory access without displaying addresses."""
    try:
        usernames = get_workspace_usernames()
        group_usernames = get_workspace_group_usernames()

        print("Google Workspace connection successful.")
        print("Directory API access: READ ONLY")
        print(f"Domain: {GOOGLE_DOMAIN}")
        print(f"Delegated account: {DELEGATED_ADMIN}")
        print(f"Reserved user addresses found: {len(usernames)}")
        print(f"Reserved group addresses found: {len(group_usernames)}")
        print(f"Unique reserved addresses: {len(usernames | group_usernames)}")
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
