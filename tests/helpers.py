"""Shared test data and fakes."""

from unittest.mock import AsyncMock

from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cookperfect.const import DOMAIN, SERVICE_UUID

ADDRESS = "20:73:6A:10:0C:A6"
TITLE = "CookPerfect 0CA6"

PAYLOAD_1 = bytes.fromhex("e752000034540000815500003e570000505f0000")
PAYLOAD_2 = bytes.fromhex("56530000a3540000f05500003e570000505f0000")
PAYLOAD_3 = bytes.fromhex("5653000012550000f0550000ad570000505f0000")

KEYS = ("core", "ambient", "needle_1", "needle_2", "needle_3", "needle_4")
CONNECTED = {
    "core": "21.223",
    "ambient": "24.4",
    "needle_1": "21.223",
    "needle_2": "21.556",
    "needle_3": "21.889",
    "needle_4": "22.334",
}
UNAVAILABLE = dict.fromkeys(KEYS, "unavailable")


def service_info(
    *,
    name="cookp",
    address=ADDRESS,
    service_uuids=(SERVICE_UUID,),
    connectable=True,
):
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=list(service_uuids),
        source="local",
        device=BLEDevice(address, name, {}),
        advertisement=None,
        connectable=connectable,
        time=0.0,
        tx_power=None,
    )


def config_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS},
    )


class FakeClient:
    def __init__(self):
        self.read_gatt_char = AsyncMock(return_value=bytearray(PAYLOAD_1))
        self.start_notify = AsyncMock()
        self.stop_notify = AsyncMock()
        self.disconnect = AsyncMock()

    def notify(self, payload):
        self.start_notify.call_args.args[1](None, bytearray(payload))


async def setup(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def readings(hass):
    registry = er.async_get(hass)
    return {
        key: hass.states.get(
            registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_{key}")
        ).state
        for key in KEYS
    }


def advertisement_callback(stack):
    return stack[0].call_args.args[1]


async def advertise(hass, stack, **kwargs):
    advertisement_callback(stack)(service_info(**kwargs))
    await hass.async_block_till_done(wait_background_tasks=True)
