import sys

from loguru import logger

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        serialize=True,
        backtrace=False,
        diagnose=False,
    )


def get_logger(**context: object):
    return logger.bind(**context)
