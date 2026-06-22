"""Structured logging for OpenLearning.

Usage:
    from openlearning.log import get_logger
    logger = get_logger("Collector")
    logger.info("Collected %d resources", count)
    logger.error("Failed to fetch: %s", url, exc_info=True)
"""

from __future__ import annotations

import logging
import sys

_INITIALIZED = False


def _init_root() -> None:
    """Initialize root logger once."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    root = logging.getLogger("openlearning")
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the 'openlearning' namespace."""
    _init_root()
    return logging.getLogger(f"openlearning.{name}")
