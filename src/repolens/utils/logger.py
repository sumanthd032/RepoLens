"""Rich-powered logging for RepoLens.

All modules should obtain their logger via :func:`get_logger`. The first call configures
the ``repolens`` logger with a single :class:`~rich.logging.RichHandler`; subsequent calls
reuse it. The level defaults to the value in :class:`~repolens.config.Config` but can be
overridden explicitly (useful for tests and the CLI ``--verbose`` flag).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.logging import RichHandler

if TYPE_CHECKING:
    from collections.abc import Iterable

_ROOT_NAME = "repolens"
_configured = False


def configure_logging(level: str | int = "INFO", *, force: bool = False) -> None:
    """Attach a :class:`RichHandler` to the ``repolens`` logger exactly once.

    Args:
        level: Logging level name (e.g. ``"DEBUG"``) or numeric level.
        force: Reconfigure even if logging was already set up (used by tests).
    """
    global _configured
    if _configured and not force:
        logging.getLogger(_ROOT_NAME).setLevel(_coerce_level(level))
        return

    logger = logging.getLogger(_ROOT_NAME)
    # Replace any existing handlers so repeated forced calls do not stack output.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=False,
        log_time_format="[%X]",
    )
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    logger.addHandler(handler)
    logger.setLevel(_coerce_level(level))
    # Keep RepoLens logs out of the root logger to avoid duplicate lines.
    logger.propagate = False
    _configured = True


def get_logger(name: str | None = None, *, level: str | int | None = None) -> logging.Logger:
    """Return a namespaced child of the ``repolens`` logger.

    Args:
        name: Sub-logger name, e.g. ``"ingestion.parser"``. ``None`` returns the root
            ``repolens`` logger.
        level: Optional level override applied to the ``repolens`` logger.
    """
    if not _configured:
        configure_logging(level if level is not None else _default_level())
    elif level is not None:
        logging.getLogger(_ROOT_NAME).setLevel(_coerce_level(level))

    if name is None or name == _ROOT_NAME:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def _default_level() -> str:
    """Read the configured log level, defaulting to ``INFO`` if config fails to load."""
    try:
        from repolens.config import get_config

        return get_config().log_level
    except Exception:  # pragma: no cover - defensive: never let logging setup crash
        return "INFO"


def _coerce_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return logging.getLevelNamesMapping().get(level.upper(), logging.INFO)


def _silence(names: Iterable[str]) -> None:  # pragma: no cover - convenience helper
    """Raise the level of noisy third-party loggers."""
    for name in names:
        logging.getLogger(name).setLevel(logging.WARNING)
