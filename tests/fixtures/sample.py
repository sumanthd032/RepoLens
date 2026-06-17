"""A sample Python module for parser tests."""

import os
from typing import Optional


GREETING = "hello"


def top_level(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class Greeter:
    """Greets people by name."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self, loud: bool = False) -> str:
        """Return a greeting, optionally shouted."""
        message = f"{GREETING}, {self.name}"
        if loud:
            return message.upper()
        return message


def find_config(start: str) -> Optional[str]:
    # Walk upward looking for a config file.
    current = start
    while current:
        candidate = os.path.join(current, ".repolens.toml")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None
