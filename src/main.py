"""Main entry point for the Shore IT Onboarding application."""

import logging
from pathlib import Path

from src.console import run_console

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure application logging."""

    LOG_DIR.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    """Run the Shore IT Onboarding application."""

    configure_logging()

    logger.info("Shore IT Onboarding application started.")

    run_console()

    logger.info("Shore IT Onboarding application stopped.")


if __name__ == "__main__":
    main()