import logging

from app.core.logging import RedactTokens


def test_link_tokens_are_masked_in_access_logs() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", "/?t=secret.token&start=step_1", "1.1", 200),
        None,
    )
    RedactTokens().filter(record)
    assert "secret" not in record.getMessage()
    assert "/?t=***&start=step_1" in record.getMessage()
    shared = logging.LogRecord("x", logging.INFO, __file__, 1, "GET /?share=abc.def", None, None)
    RedactTokens().filter(shared)
    assert shared.getMessage() == "GET /?share=***"
