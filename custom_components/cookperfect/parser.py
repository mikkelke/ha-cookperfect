"""Decode the temperature characteristic of a CookPerfect receiver."""

from __future__ import annotations

import struct
from collections.abc import Sequence

NEEDLE_COUNT = 4
AMBIENT_INDEX = 4
MIN_TEMPERATURE = -40.0
MAX_TEMPERATURE = 400.0

# Five little-endian uint32 values in milli-degrees Celsius: needles 1-4, then ambient.
_PAYLOAD = struct.Struct("<5I")


def parse_temperatures(data: bytes | bytearray) -> tuple[float | None, ...]:
    """Return the five readings in degrees Celsius, None where implausible."""
    if len(data) != _PAYLOAD.size:
        raise ValueError(f"expected {_PAYLOAD.size} bytes, got {len(data)}")
    return tuple(_plausible(raw / 1000) for raw in _PAYLOAD.unpack(data))


def _plausible(celsius: float) -> float | None:
    return celsius if MIN_TEMPERATURE <= celsius <= MAX_TEMPERATURE else None


def core_temperature(temperatures: Sequence[float | None]) -> float | None:
    """Return the coldest valid needle reading, which is the core of the meat."""
    return min(
        (value for value in temperatures[:NEEDLE_COUNT] if value is not None),
        default=None,
    )
