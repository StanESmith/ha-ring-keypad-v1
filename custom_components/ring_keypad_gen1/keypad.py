"""Bridges the Gen 1 keypad (via Z-Wave JS) and an alarm_control_panel."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started

from .const import (
    CC_ENTRY_CONTROL,
    CC_INDICATOR,
    CHIME_RESTORE_DELAY,
    CONF_ALARM_ENTITY,
    CONF_KEYPAD_DEVICE,
    DEFAULT_OPTIONS,
    EC_CANCEL,
    EVENT_ACTION_FAILED,
    EVENT_ARM_AWAY,
    EVENT_ARM_HOME,
    EVENT_CANCEL,
    EVENT_CODE_ENTERED,
    EVENT_DISARM,
    OPT_CODE_TIMEOUT,
    SIGNAL_KEYPAD_EVENT,
)
from .logic import (
    ACTION_ARM_AWAY,
    ACTION_ARM_HOME,
    ACTION_DISARM,
    CodeBuffer,
    handle_entry_control,
    indicator_for_state,
)

_LOGGER = logging.getLogger(__name__)

ZWAVE_DOMAIN = "zwave_js"

_ACTION_EVENT = {
    ACTION_DISARM: EVENT_DISARM,
    ACTION_ARM_HOME: EVENT_ARM_HOME,
    ACTION_ARM_AWAY: EVENT_ARM_AWAY,
}


class KeypadController:
    """Listens to the keypad and the alarm panel and keeps them in sync."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.device_id: str = entry.data[CONF_KEYPAD_DEVICE]
        self.alarm_entity: str = entry.data[CONF_ALARM_ENTITY]
        self.options: dict[str, Any] = {**DEFAULT_OPTIONS, **entry.options}
        self.buffer = CodeBuffer(max_age=float(self.options[OPT_CODE_TIMEOUT]))
        self._unsubs: list[CALLBACK_TYPE] = []
        self._restore_timer: CALLBACK_TYPE | None = None
        self._zwave_identifiers: set[tuple[str, str]] = set()

    @property
    def signal(self) -> str:
        return SIGNAL_KEYPAD_EVENT.format(self.entry.entry_id)

    async def async_start(self) -> None:
        self._remember_identifiers()
        self._unsubs.append(
            self.hass.bus.async_listen(
                "zwave_js_notification", self._handle_zwave_event
            )
        )
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.alarm_entity], self._handle_alarm_change
            )
        )
        self._unsubs.append(async_at_started(self.hass, self._push_current_state))
        self._track_node_status()
        _LOGGER.debug(
            "Ring keypad %s following %s (current state: %s)",
            self.device_id,
            self.alarm_entity,
            getattr(self.hass.states.get(self.alarm_entity), "state", "missing"),
        )
        if self.hass.is_running and self.hass.states.get(self.alarm_entity) is None:
            _LOGGER.warning(
                "Alarm entity %s does not exist; the keypad will not show its state",
                self.alarm_entity,
            )

    @callback
    def async_stop(self) -> None:
        self._cancel_restore_timer()
        while self._unsubs:
            self._unsubs.pop()()

    # ---- which registry device is the keypad -----------------------------
    #
    # The device id stored at setup can go stale (the node is re-included, or a
    # second registry device ends up sharing the node's Z-Wave identifiers).
    # Zwave JS reports events under, and only accepts commands for, the device
    # that belongs to its own config entry, so resolve that one by identifier
    # every time instead of trusting the stored id.

    def _remember_identifiers(self) -> None:
        stored = dr.async_get(self.hass).async_get(self.device_id)
        if stored is not None:
            self._zwave_identifiers = {
                i for i in stored.identifiers if i[0] == ZWAVE_DOMAIN
            }

    def _node_devices(self) -> list[dr.DeviceEntry]:
        """The keypad's Z-Wave JS device(s), found by Z-Wave identifier."""
        reg = dr.async_get(self.hass)
        found: dict[str, dr.DeviceEntry] = {}
        if self._zwave_identifiers:
            for zw_entry in self.hass.config_entries.async_entries(ZWAVE_DOMAIN):
                for dev in dr.async_entries_for_config_entry(reg, zw_entry.entry_id):
                    if dev.identifiers & self._zwave_identifiers:
                        found[dev.id] = dev
        return list(found.values())

    @property
    def zwave_device_id(self) -> str:
        """Device id to send Z-Wave commands to."""
        devices = self._node_devices()
        if devices:
            return devices[0].id
        _LOGGER.warning(
            "No Z-Wave JS device found for keypad %s; using stored device %s",
            self._zwave_identifiers or "?",
            self.device_id,
        )
        return self.device_id

    def _is_our_device(self, device_id: str | None) -> bool:
        if device_id is None:
            return False
        return device_id == self.device_id or any(
            device_id == dev.id for dev in self._node_devices()
        )

    def _track_node_status(self) -> None:
        """Re-show the alarm state when the keypad's node comes back alive.

        The keypad is FLiRS and can drop off the mesh; indicator commands sent
        while it was dead are lost, so push the state again once it answers.
        """
        ent_reg = er.async_get(self.hass)
        ids = [
            ent.entity_id
            for dev in self._node_devices()
            for ent in er.async_entries_for_device(ent_reg, dev.id)
            if ent.platform == ZWAVE_DOMAIN
            and ent.domain == "sensor"
            and ent.entity_id.endswith("_node_status")
        ]
        if ids:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, ids, self._handle_node_status
                )
            )

    @callback
    def _handle_node_status(self, event: Event[EventStateChangedData]) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        if new is None or new.state != "alive":
            return
        if old is not None and old.state == "alive":
            return
        _LOGGER.debug("Keypad node is alive again; re-sending alarm state")
        self._push_current_state(self.hass)

    # ---- keypad -> alarm -------------------------------------------------

    @callback
    def _handle_zwave_event(self, event: Event) -> None:
        data = event.data
        if data.get("command_class") != CC_ENTRY_CONTROL:
            return
        if not self._is_our_device(data.get("device_id")):
            return
        event_type = int(data.get("event_type", -1))
        event_data = data.get("event_data")

        if event_type == EC_CANCEL:
            self._fire(EVENT_CANCEL)
        elif event_type in (1, 2) and event_data:
            self._fire(EVENT_CODE_ENTERED)

        action = handle_entry_control(self.buffer, event_type, event_data)
        if action is not None:
            self.hass.async_create_task(
                self._async_run_action(action.action, action.code)
            )

    async def _async_run_action(self, service: str, code: str | None) -> None:
        service_data: dict[str, Any] = {ATTR_ENTITY_ID: self.alarm_entity}
        if code:
            service_data[ATTR_CODE] = code
        try:
            await self.hass.services.async_call(
                "alarm_control_panel", service, service_data, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Keypad %s on %s failed: %s", service, self.alarm_entity, err
            )
            self._fire(EVENT_ACTION_FAILED, {"action": service})
            # Re-show the real state so the keypad doesn't look like it armed.
            await self._async_send_state(self.hass.states.get(self.alarm_entity))
            return
        self._fire(_ACTION_EVENT[service])

    @callback
    def _fire(self, event_type: str, attrs: dict[str, Any] | None = None) -> None:
        # Codes are deliberately never included in events.
        async_dispatcher_send(self.hass, self.signal, event_type, attrs or {})

    # ---- alarm -> keypad -------------------------------------------------

    @callback
    def _handle_alarm_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        _LOGGER.debug(
            "%s changed to %s",
            self.alarm_entity,
            getattr(new_state, "state", None),
        )
        self.hass.async_create_task(self._async_send_state(new_state))

    @callback
    def _push_current_state(self, _hass: HomeAssistant) -> None:
        self.hass.async_create_task(
            self._async_send_state(self.hass.states.get(self.alarm_entity))
        )

    async def _async_send_state(self, state) -> None:
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug("Not updating keypad: alarm state is %s", state)
            return
        value = indicator_for_state(state.state, self.options)
        if value is None:
            _LOGGER.debug("No indicator value configured for state %s", state.state)
            return
        self._cancel_restore_timer()
        await self.async_set_indicator(value)

    # ---- chimes ----------------------------------------------------------

    async def async_chime(self, value: int) -> None:
        """Play a chime, then put the alarm state back on the lights."""
        self._cancel_restore_timer()
        await self.async_set_indicator(value)
        self._restore_timer = async_call_later(
            self.hass, CHIME_RESTORE_DELAY, self._restore_after_chime
        )

    async def _restore_after_chime(self, _now) -> None:
        self._restore_timer = None
        await self._async_send_state(self.hass.states.get(self.alarm_entity))

    @callback
    def _cancel_restore_timer(self) -> None:
        if self._restore_timer is not None:
            self._restore_timer()
            self._restore_timer = None

    async def async_set_indicator(self, value: int) -> None:
        device_id = self.zwave_device_id
        _LOGGER.debug("Setting keypad %s indicator to %s", device_id, value)
        try:
            await self.hass.services.async_call(
                "zwave_js",
                "set_value",
                {
                    "device_id": device_id,
                    "command_class": CC_INDICATOR,
                    "property": "value",
                    "value": value,
                },
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001 - never let a send kill the listener
            _LOGGER.warning("Could not set keypad indicator to %s: %s", value, err)
