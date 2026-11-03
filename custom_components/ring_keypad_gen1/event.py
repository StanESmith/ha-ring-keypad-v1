"""Event entity that reports keypad actions (codes are never exposed)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RingKeypadConfigEntry
from .const import EVENT_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingKeypadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([KeypadEvent(hass, entry)])


class KeypadEvent(EventEntity):
    """Fires alarm_disarm / alarm_arm_home / alarm_arm_away / code_entered / ..."""

    # Named explicitly (and not as a device's entity) so the entity id stays
    # event.ring_keypad_keypad without creating a device of our own.
    _attr_has_entity_name = False
    _attr_name = "Ring Keypad Keypad"
    _attr_translation_key = "keypad"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = EVENT_TYPES

    def __init__(self, hass: HomeAssistant, entry: RingKeypadConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_keypad"
        # No device_info: since each device belongs to one config entry, giving
        # the keypad's identifiers here would create a duplicate "Ring Keypad"
        # device. The entity is linked to the Z-Wave JS device instead, once
        # it is registered (see async_added_to_hass).

    async def async_added_to_hass(self) -> None:
        ent_reg = er.async_get(self.hass)
        zwave_device_id = self._entry.runtime_data.zwave_device_id
        entity = ent_reg.async_get(self.entity_id)
        if entity is not None and entity.device_id != zwave_device_id:
            ent_reg.async_update_entity(self.entity_id, device_id=zwave_device_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._entry.runtime_data.signal, self._handle_event
            )
        )

    @callback
    def _handle_event(self, event_type: str, attrs: dict[str, Any]) -> None:
        self._trigger_event(event_type, attrs)
        self.async_write_ha_state()
