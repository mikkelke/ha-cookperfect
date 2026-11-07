"""Temperature payload decoding."""

import struct

import pytest

from custom_components.cookperfect.parser import core_temperature, parse_temperatures

from .helpers import PAYLOAD_1, PAYLOAD_2, PAYLOAD_3


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (PAYLOAD_1, (21.223, 21.556, 21.889, 22.334, 24.4)),
        (PAYLOAD_2, (21.334, 21.667, 22.0, 22.334, 24.4)),
        (PAYLOAD_3, (21.334, 21.778, 22.0, 22.445, 24.4)),
    ],
    ids=["capture-1", "capture-2", "capture-3"],
)
def test_captured_payloads(payload, expected):
    assert parse_temperatures(payload) == expected


def test_accepts_bytearray():
    assert parse_temperatures(bytearray(PAYLOAD_1))[0] == 21.223


def test_implausible_values_become_none():
    payload = struct.pack("<5I", 0, 400_000, 400_001, 0xFFFFFFFF, 24_400)
    assert parse_temperatures(payload) == (0.0, 400.0, None, None, 24.4)


@pytest.mark.parametrize(
    "payload",
    [b"", PAYLOAD_1[:-1], PAYLOAD_1 + b"\x00"],
    ids=["empty", "short", "long"],
)
def test_wrong_length_is_rejected(payload):
    with pytest.raises(ValueError):
        parse_temperatures(payload)


def test_core_is_coldest_needle():
    assert core_temperature((22.0, 21.0, 23.0, 24.0, 5.0)) == 21.0


def test_core_skips_invalid_needles_and_ambient():
    assert core_temperature((None, 22.5, None, 23.0, 5.0)) == 22.5
    assert core_temperature((None, None, None, None, 24.4)) is None
