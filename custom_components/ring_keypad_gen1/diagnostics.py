"""Diagnostics to attach to a bug report. The typed code is never included."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import RingKeypadConfigEntry
from .const import CONF_KEYPAD_DEVICE, DOMAIN

TO_REDACT = {CONF_KEYPAD_DEVICE, "device_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RingKeypadConfigEntry
) -> dict[str, Any]:
    controller = entry.runtime_data
    integration = await async_get_integration(hass, DOMAIN)
    alarm = hass.states.get(controller.alarm_entity)
    return {
        "integration_version": integration.version,
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT
        ),
        "alarm_panel": {
            "entity_id": controller.alarm_entity,
            "state": alarm.state if alarm else None,
        },
        "keypad": {
            "zwave_devices_found": len(controller._node_devices()),  # noqa: SLF001
        },
    }
