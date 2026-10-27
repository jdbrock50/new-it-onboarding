"""Tests for read-only Google Workspace directory lookups."""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.google_workspace import (
    get_workspace_group_usernames,
    get_workspace_usernames,
)


def make_service(responses, resource="users"):
    """Build a mocked Directory API service for users or groups."""
    service = MagicMock()
    directory_resource = getattr(service, resource).return_value
    directory_resource.list.return_value.execute.side_effect = responses
    return service, directory_resource


def test_collects_primary_usernames():
    response = {
        "users": [
            {"primaryEmail": "jsmith@shorecollaborative.org"},
            {"primaryEmail": "mjones@shorecollaborative.org"},
        ]
    }
    service, _ = make_service([response])
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_usernames()
    assert usernames == {"jsmith", "mjones"}


def test_collects_aliases():
    response = {
        "users": [
            {
                "primaryEmail": "jsmith@shorecollaborative.org",
                "aliases": ["john.smith@shorecollaborative.org"],
                "nonEditableAliases": ["jsmith2@shorecollaborative.org"],
            }
        ]
    }
    service, _ = make_service([response])
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_usernames()
    assert usernames == {"jsmith", "john.smith", "jsmith2"}


def test_handles_multiple_pages():
    responses = [
        {
            "users": [{"primaryEmail": "user1@shorecollaborative.org"}],
            "nextPageToken": "page-two",
        },
        {"users": [{"primaryEmail": "user2@shorecollaborative.org"}]},
    ]
    service, users_resource = make_service(responses)
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_usernames()
    assert usernames == {"user1", "user2"}
    assert users_resource.list.call_count == 2
    assert users_resource.list.call_args_list[1].kwargs["pageToken"] == "page-two"


def test_ignores_addresses_outside_shore_domain():
    response = {
        "users": [
            {
                "primaryEmail": "jsmith@shorecollaborative.org",
                "aliases": ["jsmith@example.org"],
            }
        ]
    }
    service, _ = make_service([response])
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_usernames()
    assert usernames == {"jsmith"}


def test_normalizes_case_and_removes_duplicates():
    response = {
        "users": [
            {
                "primaryEmail": "JSmith@shorecollaborative.org",
                "aliases": ["jsmith@shorecollaborative.org"],
            }
        ]
    }
    service, _ = make_service([response])
    with patch("src.google_workspace.create_directory_service", return_value=service):
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
        patch("src.google_workspace.create_directory_service", return_value=service),
        pytest.raises(HttpError),
    ):
        get_workspace_usernames()


def test_collects_group_addresses():
    response = {
        "groups": [
            {"email": "staff@shorecollaborative.org"},
            {"email": "technology@shorecollaborative.org"},
        ]
    }
    service, groups_resource = make_service([response], resource="groups")
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_group_usernames()
    assert usernames == {"staff", "technology"}
    groups_resource.list.assert_called_once()
    assert groups_resource.list.call_args.kwargs["domain"] == "shorecollaborative.org"


def test_collects_group_aliases():
    response = {
        "groups": [
            {
                "email": "staff@shorecollaborative.org",
                "aliases": ["allstaff@shorecollaborative.org"],
                "nonEditableAliases": ["faculty@shorecollaborative.org"],
            }
        ]
    }
    service, _ = make_service([response], resource="groups")
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_group_usernames()
    assert usernames == {"staff", "allstaff", "faculty"}


def test_group_pagination():
    responses = [
        {
            "groups": [{"email": "group1@shorecollaborative.org"}],
            "nextPageToken": "next-groups",
        },
        {"groups": [{"email": "group2@shorecollaborative.org"}]},
    ]
    service, groups_resource = make_service(responses, resource="groups")
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_group_usernames()
    assert usernames == {"group1", "group2"}
    assert groups_resource.list.call_count == 2
    assert groups_resource.list.call_args_list[1].kwargs["pageToken"] == "next-groups"


def test_group_addresses_are_normalized_and_domain_filtered():
    response = {
        "groups": [
            {
                "email": "STAFF@shorecollaborative.org",
                "aliases": [
                    "staff@shorecollaborative.org",
                    "external@example.org",
                    "  HELP@SHORECOLLABORATIVE.ORG  ",
                ],
            }
        ]
    }
    service, _ = make_service([response], resource="groups")
    with patch("src.google_workspace.create_directory_service", return_value=service):
        usernames = get_workspace_group_usernames()
    assert usernames == {"staff", "help"}


def test_group_api_error_propagates():
    response = MagicMock()
    response.status = 403
    error = HttpError(resp=response, content=b'{"error": "Forbidden"}')
    service, _ = make_service([error], resource="groups")
    with (
        patch("src.google_workspace.create_directory_service", return_value=service),
        pytest.raises(HttpError),
    ):
        get_workspace_group_usernames()


def test_group_second_page_error_propagates():
    response = MagicMock()
    response.status = 500
    error = HttpError(resp=response, content=b'{"error": "Server error"}')
    responses = [
        {
            "groups": [{"email": "staff@shorecollaborative.org"}],
            "nextPageToken": "next",
        },
        error,
    ]
    service, groups_resource = make_service(responses, resource="groups")
    with (
        patch("src.google_workspace.create_directory_service", return_value=service),
        pytest.raises(HttpError),
    ):
        get_workspace_group_usernames()
    assert groups_resource.list.call_count == 2
