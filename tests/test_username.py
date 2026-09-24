"""Tests for Shore username generation."""

from src.username import (
    generate_base_username,
    generate_middle_initial_username,
    normalize_name,
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