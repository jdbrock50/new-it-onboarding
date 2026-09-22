"""Main application entry point."""

import logging


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> None:
    """Run the application."""
    configure_logging()

    logging.info("Application started.")
    print("Python project is ready.")


if __name__ == "__main__":
    main()
