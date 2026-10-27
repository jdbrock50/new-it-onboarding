
"""Tests for read-only Google Workspace directory lookups."""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.google_workspace import get_workspace_usernames


def make_service(responses):
    """Build a mocked Directory API service."""
    service = MagicMock()
    users_resource = service.users.return_value

    users_resource.list.return_value.execute.side_effect = responses

    return service, users_resource


def test_collects_primary_usernames():
    response = {
        "users": [
            {"primaryEmail": "jsmith@shorecollaborative.org"},
            {"primaryEmail": "mjones@shorecollaborative.org"},
        ]
    }

    service, _ = make_service([response])

    with patch(
        "src.google_workspace.create_directory_service",
        return_value=service,
    ):
        usernames = get_workspace_usernames()

    assert usernames == {"jsmith", "mjones"}


def test_collects_aliases():
    response = {
        "users": [
            {
                "primaryEmail": "jsmith@shorecollaborative.org",
                "aliases": [
                    "john.smith@shorecollaborative.org",
                ],
                "nonEditableAliases": [
                    "jsmith2@shorecollaborative.org",
                ],
            }
        ]
    }

    service, _ = make_service([response])

    with patch(
        "src.google_workspace.create_directory_service",
        return_value=service,
    ):
        usernames = get_workspace_usernames()

    assert usernames == {
        "jsmith",
        "john.smith",
        "jsmith2",
    }


def test_handles_multiple_pages():
    responses = [
        {
            "users": [
                {"primaryEmail": "user1@shorecollaborative.org"},
            ],
            "nextPageToken": "page-two",
        },
        {
            "users": [
                {"primaryEmail": "user2@shorecollaborative.org"},
            ]
        },
    ]

    service, users_resource = make_service(responses)

    with patch(
        "src.google_workspace.create_directory_service",
        return_value=service,
    ):
        usernames = get_workspace_usernames()

    assert usernames == {"user1", "user2"}
    assert users_resource.list.call_count == 2

    assert users_resource.list.call_args_list[1].kwargs[
        "pageToken"
    ] == "page-two"


def test_ignores_addresses_outside_shore_domain():
    response = {
        "users": [
            {
                "primaryEmail": "jsmith@shorecollaborative.org",
                "aliases": [
                    "jsmith@example.org",
                ],
            }
        ]
    }

    service, _ = make_service([response])

    with patch(
        "src.google_workspace.create_directory_service",
        return_value=service,
    ):
        usernames = get_workspace_usernames()

    assert usernames == {"jsmith"}


def test_normalizes_case_and_removes_duplicates():
    response = {
        "users": [
            {
                "primaryEmail": "JSmith@shorecollaborative.org",
                "aliases": [
                    "jsmith@shorecollaborative.org",
                ],
            }
        ]
    }

    service, _ = make_service([response])

    with patch(
        "src.google_workspace.create_directory_service",
        return_value=service,
    ):
        usernames = get_workspace_usernames()

    assert usernames == {"jsmith"}


def test_propagates_api_errors():
    response = MagicMock()
    response.status = 403

    error = HttpError(
        resp=response,
        content=b'{"error": {"message": "Forbidden"}}',
    )

    service, _ = make_service([error])

    with (
        patch(
            "src.google_workspace.create_directory_service",
            return_value=service,
        ),
        pytest.raises(HttpError),
    ):
        get_workspace_usernames()
