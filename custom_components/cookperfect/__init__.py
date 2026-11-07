"""Read probe temperatures from a CookPerfect receiver over Bluetooth."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .connection import CookPerfectConnection

PLATFORMS = [Platform.SENSOR]

type CookPerfectConfigEntry = ConfigEntry[CookPerfectConnection]


async def async_setup_entry(hass: HomeAssistant, entry: CookPerfectConfigEntry) -> bool:
    connection = CookPerfectConnection(hass, entry.data[CONF_ADDRESS], entry.title)
    entry.runtime_data = connection
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    connection.async_start()
    entry.async_on_unload(connection.async_stop)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CookPerfectConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
