"""Typed error hierarchy.

Every user-facing failure is one of these; the CLI maps them to actionable
messages and exit codes. Nothing in this module guesses or fabricates data.
"""

from __future__ import annotations


class DopplerGeoError(Exception):
    """Base class for all expected failures."""


class DataUnavailable(DopplerGeoError):
    """A required dataset cannot be obtained from any configured source."""

    def __init__(self, what: str, *, tried: list[str] | None = None, ask: str = "") -> None:
        self.what = what
        self.tried = tried or []
        self.ask = ask
        lines = [f"Missing required data: {what}."]
        if self.tried:
            lines.append("Tried: " + ", ".join(self.tried) + ".")
        if self.ask:
            lines.append("Ask the user: " + self.ask)
        super().__init__(" ".join(lines))


class DataFormatError(DopplerGeoError):
    """A dataset exists but does not match the expected schema."""
