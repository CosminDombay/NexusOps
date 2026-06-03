import logging
from typing import Any

import structlog

from backend.app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(level=settings.log_level, format="%(levelname)s - %(asctime)s : %(message)s")
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else _human_readable_renderer
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        cache_logger_on_first_use=True,
    )


def _human_readable_renderer(logger: Any, name: str, event_dict: dict[str, Any]) -> str:
    level = str(event_dict.pop("level", "info")).upper()
    timestamp = str(event_dict.pop("timestamp", ""))
    event = str(event_dict.pop("event", "log"))
    message = event.replace("_", " ").replace(".", " ")
    reason = event_dict.pop("reason", None)
    details = []
    if reason is not None:
        details.append(f"reason={reason}")
    details.extend(f"{key}={value}" for key, value in sorted(event_dict.items()))
    suffix = f" | {' '.join(details)}" if details else ""
    return f"{level} - {timestamp} : {message}{suffix}"
