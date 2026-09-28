"""Tests for Shore username generation."""

from src.username import (
    generate_base_username,
    generate_middle_initial_username,
    normalize_name,
    resolve_username,
)


def test_normalize_accented_name():
    assert normalize_name("José") == "jose"


def test_normalize_apostrophe():
    assert normalize_name("O'Connor") == "oconnor"


def test_normalize_spaces():
    assert normalize_name("De La Cruz") == "delacruz"


def test_normalize_hyphen():
    assert normalize_name("Smith-Jones") == "smithjones"


def test_generate_accented_username():
    assert (
        generate_base_username("José", "Rodríguez")
        == "jrodriguez"
    )


def test_generate_apostrophe_username():
    assert (
        generate_base_username("Anne", "O'Connor")
        == "aoconnor"
    )


def test_generate_multiword_username():
    assert (
        generate_base_username("Maria", "De La Cruz")
        == "mdelacruz"
    )


def test_generate_middle_initial_username():
    assert (
        generate_middle_initial_username(
            "Maria",
            "L",
            "Gonzalez",
        )
        == "mlgonzalez"
    )

def test_resolve_available_base_username():
    existing = {
        "jdoe",
        "asmith",
    }

    username = resolve_username(
        first_name="Maria",
        last_name="Gonzalez",
        existing_usernames=existing,
    )

    assert username == "mgonzalez"


def test_resolve_collision_with_middle_initial():
    existing = {
        "msmith",
    }

    username = resolve_username(
        first_name="Mary",
        middle_name="Anne",
        last_name="Smith",
        existing_usernames=existing,
    )

    assert username == "masmith"


def test_resolve_collision_with_number():
    existing = {
        "msmith",
    }

    username = resolve_username(
        first_name="Mark",
        last_name="Smith",
        existing_usernames=existing,
    )

    assert username == "msmith1"


def test_resolve_multiple_number_collisions():
    existing = {
        "msmith",
        "msmith1",
        "msmith2",
        "msmith3",
    }

    username = resolve_username(
        first_name="Mark",
        last_name="Smith",
        existing_usernames=existing,
    )

    assert username == "msmith4"


def test_resolve_middle_initial_collision_falls_back_to_number():
    existing = {
        "msmith",
        "masmith",
        "msmith1",
    }

    username = resolve_username(
        first_name="Mary",
        middle_name="Anne",
        last_name="Smith",
        existing_usernames=existing,
    )

    assert username == "msmith2"


def test_resolve_username_is_case_insensitive():
    existing = {
        "MGONZALEZ",
    }

    username = resolve_username(
        first_name="Maria",
        last_name="Gonzalez",
        existing_usernames=existing,
    )

    assert username == "mgonzalez1"