import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging() -> None:
    logger = logging.getLogger()

    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
