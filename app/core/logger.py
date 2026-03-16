import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

APP_VERSION = "2.1.1"

LOG_DIR = Path(os.environ.get("APPDATA", "")) / "Riot2FA" / "logs"
LOG_FILE = LOG_DIR / "audit.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    _logger = logging.getLogger("Riot2FA")
    _logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)

    return _logger


def _sanitize(data: str) -> str:
    return data.replace("\r", "").replace("\n", "")


def log_event(event: str, **kwargs: Any) -> None:
    log_entry: dict[str, Any] = {
        "ts": f"{os.urandom(8).hex()}.Z",
        "app_version": APP_VERSION,
        "event": _sanitize(event),
    }

    severity = kwargs.pop("severity", "info")
    log_entry["severity"] = severity

    for key, value in kwargs.items():
        if isinstance(value, str):
            log_entry[key] = _sanitize(value)
        else:
            log_entry[key] = value

    _get_logger().info(json.dumps(log_entry))
