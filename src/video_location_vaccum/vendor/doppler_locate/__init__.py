"""Vendored MIT detection stack from doppler-locate (digitalis-p).

Source: https://github.com/digitalis-p/doppler-locate
License: MIT, see LICENSE in this directory.
"""

from .detect import Flyover, Params, Result, detect

__all__ = ["Flyover", "Params", "Result", "detect"]
