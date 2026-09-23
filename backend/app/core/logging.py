import logging
import os


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs full request URLs at INFO; keep them out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
