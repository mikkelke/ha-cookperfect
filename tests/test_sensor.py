"""Sensor values and entity metadata."""

import struct

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH

from custom_components.cookperfect.const import DOMAIN

from .helpers import ADDRESS, KEYS, TITLE, advertise, readings, setup

NAMES = {
    "core": "Core temperature",
    "ambient": "Ambient temperature",
    "needle_1": "Needle 1",
    "needle_2": "Needle 2",
    "needle_3": "Needle 3",
    "needle_4": "Needle 4",
}


async def test_entities_and_device(hass, stack, establish):
    entry = await setup(hass)
    await advertise(hass, stack)
    registry = er.async_get(hass)

    for key in KEYS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_{key}")
        registered = registry.async_get(entity_id)
        state = hass.states.get(entity_id)
        assert state.name == f"{TITLE} {NAMES[key]}"
        assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
        assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
        assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
        assert registered.options["sensor"]["suggested_display_precision"] == 1
        assert registered.entity_category == (
            EntityCategory.DIAGNOSTIC if key.startswith("needle") else None
        )

    device = dr.async_get(hass).async_get_device_by_connection(
        (CONNECTION_BLUETOOTH, ADDRESS), entry.entry_id
    )
    assert device.manufacturer == "CookPerfect"
    assert device.name == TITLE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            (22_000, 0xFFFFFFFF, 21_000, 23_000, 0xFFFFFFFF),
            {
                "core": "21.0",
                "ambient": "unknown",
                "needle_1": "22.0",
                "needle_2": "unknown",
                "needle_3": "21.0",
                "needle_4": "23.0",
            },
        ),
        (
            (0xFFFFFFFF,) * 4 + (24_400,),
            {
                "core": "unknown",
                "ambient": "24.4",
                "needle_1": "unknown",
                "needle_2": "unknown",
                "needle_3": "unknown",
                "needle_4": "unknown",
            },
        ),
    ],
)
async def test_implausible_needle_values_are_unknown(
    hass, stack, establish, client, raw, expected
):
    client.read_gatt_char.return_value = bytearray(struct.pack("<5I", *raw))
    await setup(hass)
    await advertise(hass, stack)
    assert readings(hass) == expected
