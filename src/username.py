"""Shore username generation and normalization."""

import re
import unicodedata


def normalize_name(value: str) -> str:
    """Normalize a name for use in a Shore username.

    Removes accents, spaces, apostrophes, hyphens, and other
    non-alphanumeric characters.

    Examples:
        José -> jose
        O'Connor -> oconnor
        De La Cruz -> delacruz
        Smith-Jones -> smithjones
    """

    normalized = unicodedata.normalize("NFKD", value)

    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    return re.sub(r"[^a-zA-Z0-9]", "", ascii_value).lower()


def generate_base_username(
    first_name: str,
    last_name: str,
) -> str:
    """Generate the standard Shore username."""

    normalized_first = normalize_name(first_name)
    normalized_last = normalize_name(last_name)

    if not normalized_first:
        raise ValueError("First name cannot be empty.")

    if not normalized_last:
        raise ValueError("Last name cannot be empty.")

    return f"{normalized_first[0]}{normalized_last}"


def generate_middle_initial_username(
    first_name: str,
    middle_name: str,
    last_name: str,
) -> str:
    """Generate a Shore username containing a middle initial."""

    normalized_first = normalize_name(first_name)
    normalized_middle = normalize_name(middle_name)
    normalized_last = normalize_name(last_name)

    if not normalized_middle:
        return generate_base_username(first_name, last_name)

    return (
        f"{normalized_first[0]}"
        f"{normalized_middle[0]}"
        f"{normalized_last}"
    )