"""Hold the Bluetooth link to a CookPerfect receiver and publish its readings."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, RETRY_DELAY, TEMPERATURE_UUID
from .parser import parse_temperatures

_LOGGER = logging.getLogger(__name__)


class CookPerfectConnection:
    """Connect to one receiver whenever it advertises and publish its readings."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        self.address = address
        self.temperatures: tuple[float | None, ...] | None = None
        self._hass = hass
        self._name = name
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._cancel_callbacks: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(update)
        return lambda: self._listeners.discard(update)

    @callback
    def async_start(self) -> None:
        # async_register_callback skips advertisements whose data is unchanged, and
        # this receiver always sends the same one, so retries need every advertisement.
        self._cancel_callbacks = [
            bluetooth.async_register_advertisement_callback(
                self._hass, self._async_on_advertisement, self.address
            ),
            bluetooth.async_track_unavailable(
                self._hass, self._async_on_unavailable, self.address, connectable=True
            ),
        ]

    async def async_stop(self) -> None:
        for cancel in self._cancel_callbacks:
            cancel()
        self._cancel_callbacks.clear()
        if self._task is not None:
            self._task.cancel()
            await asyncio.wait([self._task])
        await self._async_disconnect()

    @callback
    def _async_on_advertisement(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        if (
            service_info.connectable
            and self._client is None
            and not self._lock.locked()
        ):
            self._task = self._hass.async_create_background_task(
                self._async_connect(service_info.device),
                f"{DOMAIN} connect {self.address}",
            )

    @callback
    def _async_on_unavailable(
        self, _service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        # A connected receiver stops advertising, so Home Assistant reports it
        # unavailable while notifications keep arriving.
        if self._client is None:
            self._async_publish(None)

    @callback
    def _async_on_disconnect(self, client: BleakClientWithServiceCache) -> None:
        if client is self._client:
            _LOGGER.debug("%s disconnected", self.address)
            self._client = None
            self._async_publish(None)

    @callback
    def _async_on_notify(
        self, _characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        self._async_update(data)

    @callback
    def _async_update(self, data: bytes | bytearray) -> None:
        if self._client is None:
            return
        try:
            temperatures = parse_temperatures(data)
        except ValueError as err:
            _LOGGER.debug("Ignoring payload from %s: %s", self.address, err)
            return
        self._async_publish(temperatures)

    @callback
    def _async_publish(self, temperatures: tuple[float | None, ...] | None) -> None:
        self.temperatures = temperatures
        for update in tuple(self._listeners):
            update()

    async def _async_connect(self, device: BLEDevice) -> None:
        async with self._lock:
            if self._client is not None:
                return
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    self._name,
                    disconnected_callback=self._async_on_disconnect,
                )
                self._client = client
                self._async_update(await client.read_gatt_char(TEMPERATURE_UUID))
                await client.start_notify(TEMPERATURE_UUID, self._async_on_notify)
                _LOGGER.debug("%s connected", self.address)
            except Exception:
                _LOGGER.debug("Connecting to %s failed", self.address, exc_info=True)
                await self._async_disconnect()
                await asyncio.sleep(RETRY_DELAY)

    async def _async_disconnect(self) -> None:
        client, self._client = self._client, None
        self._async_publish(None)
        if client is not None:
            with suppress(Exception):
                await client.stop_notify(TEMPERATURE_UUID)
            with suppress(Exception):
                await client.disconnect()
