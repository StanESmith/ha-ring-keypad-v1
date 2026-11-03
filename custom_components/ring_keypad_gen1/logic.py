"""Home Assistant-independent keypad logic, so it can be unit tested on its own."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .const import (
    EC_AWAY,
    EC_CACHED_KEYS,
    EC_CANCEL,
    EC_DISARM,
    EC_ENTER,
    EC_HOME,
    INDICATOR_MAX,
    INDICATOR_SILENT_BIT,
    OPT_IND_ARMED_AWAY,
    OPT_IND_ARMED_HOME,
    OPT_IND_ARMING,
    OPT_IND_DISARMED,
    OPT_IND_PENDING,
    OPT_SILENT_STATUS,
    OPT_TRIGGERED_SOUND,
)

ACTION_DISARM = "alarm_disarm"
ACTION_ARM_HOME = "alarm_arm_home"
ACTION_ARM_AWAY = "alarm_arm_away"

_MODE_ACTIONS = {
    EC_DISARM: ACTION_DISARM,
    EC_HOME: ACTION_ARM_HOME,
    EC_AWAY: ACTION_ARM_AWAY,
}


@dataclass
class KeypadAction:
    """What the keypad asked for."""

    action: str  # alarm_disarm / alarm_arm_home / alarm_arm_away
    code: str | None


@dataclass
class CodeBuffer:
    """Remembers a code typed just before a mode button is pressed.

    The Gen 1 keypad sends the code either attached to the mode event, or as
    a separate "Enter"/"Cached keys" event shortly before it.
    """

    max_age: float
    clock: Callable[[], float] = time.monotonic
    _code: str | None = field(default=None, init=False)
    _at: float = field(default=0.0, init=False)

    def store(self, code: str) -> None:
        self._code = code
        self._at = self.clock()

    def clear(self) -> None:
        self._code = None

    def take(self) -> str | None:
        """Return the buffered code if still fresh, and clear it."""
        code, self._code = self._code, None
        if code is None or self.clock() - self._at > self.max_age:
            return None
        return code


def handle_entry_control(
    buffer: CodeBuffer, event_type: int, event_data: str | None
) -> KeypadAction | None:
    """Process one Entry Control notification; return an alarm action or None."""
    data = (event_data or "").strip() or None

    if event_type in (EC_CACHED_KEYS, EC_ENTER):
        if data:
            buffer.store(data)
        return None

    if event_type == EC_CANCEL:
        buffer.clear()
        return None

    action = _MODE_ACTIONS.get(event_type)
    if action is None:
        return None

    code = data or buffer.take()
    buffer.clear()
    if action == ACTION_DISARM and not code:
        # Never send a disarm without a code.
        return None
    return KeypadAction(action=action, code=code)


_STATE_OPTION = {
    "disarmed": OPT_IND_DISARMED,
    "armed_home": OPT_IND_ARMED_HOME,
    "armed_night": OPT_IND_ARMED_HOME,
    "armed_custom_bypass": OPT_IND_ARMED_HOME,
    "armed_away": OPT_IND_ARMED_AWAY,
    "armed_vacation": OPT_IND_ARMED_AWAY,
    "arming": OPT_IND_ARMING,
    "pending": OPT_IND_PENDING,
}


def indicator_for_state(state: str, options: dict) -> int | None:
    """Map an alarm_control_panel state to an Indicator value (or None to skip)."""
    if state == "triggered":
        value = int(options.get(OPT_TRIGGERED_SOUND, 4))
    else:
        opt = _STATE_OPTION.get(state)
        if opt is None:
            return None
        value = int(options.get(opt, -1))
        if options.get(OPT_SILENT_STATUS) and 0 <= value < INDICATOR_SILENT_BIT:
            value += INDICATOR_SILENT_BIT
    if value < 0 or value > INDICATOR_MAX:
        return None
    return value
