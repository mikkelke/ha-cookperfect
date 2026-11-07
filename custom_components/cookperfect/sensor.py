"""Temperature sensors for a CookPerfect receiver."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import itemgetter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CookPerfectConfigEntry
from .connection import CookPerfectConnection
from .const import DOMAIN
from .parser import AMBIENT_INDEX, NEEDLE_COUNT, core_temperature


@dataclass(frozen=True, kw_only=True)
class CookPerfectSensorDescription(SensorEntityDescription):
    value_fn: Callable[[tuple[float | None, ...]], float | None]


SENSORS = (
    CookPerfectSensorDescription(
        key="core",
        translation_key="core_temperature",
        value_fn=core_temperature,
    ),
    CookPerfectSensorDescription(
        key="ambient",
        translation_key="ambient_temperature",
        value_fn=itemgetter(AMBIENT_INDEX),
    ),
    *(
        CookPerfectSensorDescription(
            key=f"needle_{index + 1}",
            translation_key=f"needle_{index + 1}",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=itemgetter(index),
        )
        for index in range(NEEDLE_COUNT)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookPerfectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        CookPerfectSensor(entry.runtime_data, entry.title, description)
        for description in SENSORS
    )


class CookPerfectSensor(SensorEntity):
    entity_description: CookPerfectSensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        connection: CookPerfectConnection,
        title: str,
        description: CookPerfectSensorDescription,
    ) -> None:
        self.entity_description = description
        self._connection = connection
        self._attr_unique_id = f"{connection.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, connection.address)},
            connections={(CONNECTION_BLUETOOTH, connection.address)},
            manufacturer="CookPerfect",
            name=title,
        )

    @property
    def available(self) -> bool:
        return self._connection.temperatures is not None

    @property
    def native_value(self) -> float | None:
        if (temperatures := self._connection.temperatures) is None:
            return None
        return self.entity_description.value_fn(temperatures)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._connection.async_add_listener(self.async_write_ha_state)
        )
