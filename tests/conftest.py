"""Shared Home Assistant integration fixtures."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components import bluetooth

from .helpers import FakeClient


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def bluetooth_loaded(hass):
    hass.config.components.update({"usb", "bluetooth", "bluetooth_adapters"})


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def establish(client):
    with patch(
        "custom_components.cookperfect.connection.establish_connection",
        AsyncMock(return_value=client),
    ) as establish:
        yield establish


@pytest.fixture
def stack():
    """Capture the callbacks the integration registers with Bluetooth."""
    with (
        patch.object(
            bluetooth, "async_register_advertisement_callback", Mock()
        ) as register,
        patch.object(bluetooth, "async_track_unavailable", Mock()) as track,
    ):
        yield register, track
