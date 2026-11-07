"""Bluetooth discovery and manual setup of a receiver."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from custom_components.cookperfect.const import DOMAIN, SERVICE_UUID

from .helpers import ADDRESS, TITLE, config_entry, service_info

OTHER = "20:73:6A:10:0C:B7"


@pytest.fixture(autouse=True)
def no_setup():
    with patch("custom_components.cookperfect.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def discovered():
    with patch(
        "custom_components.cookperfect.config_flow.async_discovered_service_info"
    ) as discovered:
        yield discovered


async def test_bluetooth_discovery_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": TITLE}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_aborts_when_configured(hass):
    config_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_offers_unconfigured_receivers(hass, discovered):
    config_entry().add_to_hass(hass)
    discovered.return_value = [
        service_info(),
        service_info(address=OTHER),
        service_info(name="other", address="20:73:6A:10:0C:C8", service_uuids=()),
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS].container == {
        OTHER: "CookPerfect 0CB7"
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: OTHER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "CookPerfect 0CB7"
    assert result["data"] == {CONF_ADDRESS: OTHER}
    assert result["result"].unique_id == OTHER


@pytest.mark.parametrize(
    "info",
    [
        service_info(service_uuids=()),
        service_info(name="unnamed", service_uuids=(SERVICE_UUID,)),
    ],
)
async def test_user_step_matches_on_name_or_service_uuid(hass, discovered, info):
    discovered.return_value = [info]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert list(result["data_schema"].schema[CONF_ADDRESS].container) == [ADDRESS]


async def test_user_step_without_receivers_aborts(hass, discovered):
    discovered.return_value = [service_info(name="other", service_uuids=())]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_aborts_when_configured_meanwhile(hass, discovered):
    discovered.return_value = [service_info()]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    config_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
