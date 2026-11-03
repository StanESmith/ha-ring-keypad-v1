"""Ring Alarm Keypad (1st Gen) for Home Assistant.

Turns a Ring Gen 1 keypad paired to Z-Wave JS into a keypad for any
alarm_control_panel: PIN + mode buttons arm/disarm the panel, and the panel's
state is shown on the keypad's lights.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import CHIME_DOOR, DOMAIN, INDICATOR_MAX
from .keypad import KeypadController

PLATFORMS: list[Platform] = [Platform.EVENT]

type RingKeypadConfigEntry = ConfigEntry[KeypadController]

SERVICE_SET_INDICATOR = "set_indicator"
SET_INDICATOR_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Required("value"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=INDICATOR_MAX)
        ),
    }
)

SERVICE_CHIME = "chime"
CHIME_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Optional("value", default=CHIME_DOOR): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=INDICATOR_MAX)
        ),
    }
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _controller(hass: HomeAssistant, call: ServiceCall) -> KeypadController:
    entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
    if (
        entry is None
        or entry.domain != DOMAIN
        or not isinstance(getattr(entry, "runtime_data", None), KeypadController)
    ):
        raise ServiceValidationError("Unknown or unloaded Ring Keypad config entry")
    return entry.runtime_data


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the integration's actions."""

    async def _set_indicator(call: ServiceCall) -> None:
        await _controller(hass, call).async_set_indicator(call.data["value"])

    async def _chime(call: ServiceCall) -> None:
        await _controller(hass, call).async_chime(call.data["value"])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_INDICATOR, _set_indicator, schema=SET_INDICATOR_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CHIME, _chime, schema=CHIME_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RingKeypadConfigEntry) -> bool:
    controller = KeypadController(hass, entry)
    entry.runtime_data = controller
    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RingKeypadConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_stop()
    return unloaded


async def _async_reload_on_options(
    hass: HomeAssistant, entry: RingKeypadConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
