"""Setup, connection handling and unload of a receiver entry."""

import asyncio
from unittest.mock import patch

import pytest
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache
from homeassistant.config_entries import ConfigEntryState

from custom_components.cookperfect.const import TEMPERATURE_UUID

from .helpers import (
    ADDRESS,
    CONNECTED,
    PAYLOAD_1,
    PAYLOAD_2,
    TITLE,
    UNAVAILABLE,
    FakeClient,
    advertise,
    advertisement_callback,
    readings,
    service_info,
    setup,
)


async def test_setup_registers_callbacks_and_unload_releases_them(
    hass, stack, establish
):
    register, track = stack
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert register.call_args.args[0] is hass
    assert register.call_args.args[2] == ADDRESS
    assert track.call_args.args[0] is hass
    assert track.call_args.args[2] == ADDRESS
    assert track.call_args.kwargs == {"connectable": True}
    assert readings(hass) == UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    register.return_value.assert_called_once_with()
    track.return_value.assert_called_once_with()
    establish.assert_not_called()


async def test_connects_on_advertisement_and_publishes_readings(
    hass, stack, establish, client
):
    await setup(hass)
    await advertise(hass, stack)

    establish.assert_awaited_once()
    assert establish.call_args.args[0] is BleakClientWithServiceCache
    assert establish.call_args.args[1].address == ADDRESS
    assert establish.call_args.args[2] == TITLE
    client.read_gatt_char.assert_awaited_once_with(TEMPERATURE_UUID)
    client.start_notify.assert_awaited_once()
    assert client.start_notify.call_args.args[0] == TEMPERATURE_UUID
    assert readings(hass) == CONNECTED

    client.notify(PAYLOAD_2)
    assert readings(hass) == {
        "core": "21.334",
        "ambient": "24.4",
        "needle_1": "21.334",
        "needle_2": "21.667",
        "needle_3": "22.0",
        "needle_4": "22.334",
    }


async def test_ignores_malformed_notification(hass, stack, establish, client):
    await setup(hass)
    await advertise(hass, stack)
    client.notify(PAYLOAD_1[:-1])
    assert readings(hass) == CONNECTED


async def test_advertisements_while_connected_do_not_reconnect(hass, stack, establish):
    await setup(hass)
    await advertise(hass, stack)
    await advertise(hass, stack)
    assert establish.await_count == 1


async def test_ignores_non_connectable_advertisement(hass, stack, establish):
    await setup(hass)
    await advertise(hass, stack, connectable=False)
    establish.assert_not_called()
    assert readings(hass) == UNAVAILABLE


async def test_disconnect_hides_readings_and_next_advertisement_reconnects(
    hass, stack, establish, client
):
    await setup(hass)
    await advertise(hass, stack)

    establish.call_args.kwargs["disconnected_callback"](FakeClient())
    assert readings(hass) == CONNECTED

    establish.call_args.kwargs["disconnected_callback"](client)
    assert readings(hass) == UNAVAILABLE

    await advertise(hass, stack)
    assert establish.await_count == 2
    assert readings(hass) == CONNECTED


async def test_notification_after_disconnect_is_ignored(hass, stack, establish, client):
    await setup(hass)
    await advertise(hass, stack)
    establish.call_args.kwargs["disconnected_callback"](client)

    client.notify(PAYLOAD_2)
    assert readings(hass) == UNAVAILABLE


async def test_unavailable_event_keeps_a_connected_receiver(hass, stack, establish):
    await setup(hass)
    await advertise(hass, stack)
    stack[1].call_args.args[1](service_info())
    assert readings(hass) == CONNECTED


@pytest.mark.parametrize("error", [BleakError("no free slot"), TimeoutError()])
async def test_failed_connect_pauses_before_next_attempt(
    hass, stack, establish, client, error
):
    establish.side_effect = [error, client]
    with patch("custom_components.cookperfect.connection.RETRY_DELAY", 0.05):
        await setup(hass)
        advertisement_callback(stack)(service_info())
        advertisement_callback(stack)(service_info())
        await hass.async_block_till_done(wait_background_tasks=True)
        assert establish.await_count == 1
        assert readings(hass) == UNAVAILABLE

        await advertise(hass, stack)
    assert establish.await_count == 2
    assert readings(hass) == CONNECTED


async def test_failure_after_connecting_disconnects_and_hides_readings(
    hass, stack, establish, client
):
    client.start_notify.side_effect = BleakError("no notify")
    with patch("custom_components.cookperfect.connection.RETRY_DELAY", 0):
        await setup(hass)
        await advertise(hass, stack)
    client.stop_notify.assert_awaited_once_with(TEMPERATURE_UUID)
    client.disconnect.assert_awaited_once_with()
    assert readings(hass) == UNAVAILABLE


async def test_unload_stops_notifications_and_disconnects(
    hass, stack, establish, client
):
    entry = await setup(hass)
    await advertise(hass, stack)

    assert await hass.config_entries.async_unload(entry.entry_id)
    client.stop_notify.assert_awaited_once_with(TEMPERATURE_UUID)
    client.disconnect.assert_awaited_once_with()


@pytest.mark.parametrize("stalls_after_connecting", [False, True])
async def test_unload_cancels_connect_in_progress(
    hass, stack, establish, client, stalls_after_connecting
):
    started = asyncio.Event()

    async def stall(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    if stalls_after_connecting:
        client.read_gatt_char.side_effect = stall
    else:
        establish.side_effect = stall
    entry = await setup(hass)
    advertisement_callback(stack)(service_info())
    await started.wait()

    async with asyncio.timeout(5):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert client.disconnect.await_count == stalls_after_connecting
