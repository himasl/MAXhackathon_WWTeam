import logging
import os
import re

# Signed login (?t=...) and parent-link (?share=...) tokens must not end up in logs.
_SECRET_QUERY = re.compile(r"([?&](?:t|share)=)[^&\s\"]+")


class RedactTokens(logging.Filter):
    """Masks link tokens in uvicorn access log lines (``GET /?t=<token>``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SECRET_QUERY.sub(r"\1***", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        elif isinstance(record.msg, str):
            record.msg = _SECRET_QUERY.sub(r"\1***", record.msg)
        return True


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs full request URLs at INFO; keep them out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").addFilter(RedactTokens())
