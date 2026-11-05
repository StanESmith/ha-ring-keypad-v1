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
    OPT_SILENT_ARMDISARM,
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

# "Settled" arm/disarm states vs the transitional exit/entry-delay countdown.
# The two silent options mute complementary sets of these (triggered is never
# muted here; it has its own OPT_TRIGGERED_SOUND control).
_SETTLED_STATES = frozenset(
    {
        "disarmed",
        "armed_home",
        "armed_night",
        "armed_custom_bypass",
        "armed_away",
        "armed_vacation",
    }
)
_DELAY_STATES = frozenset({"arming", "pending"})


def _mute_sound(state: str, options: dict) -> bool:
    """Whether the keypad sound for this state should be muted (the +32 bit).

    - OPT_SILENT_STATUS silences the settled armed/disarmed states. Indicator
      values 1/2/3 make the keypad speak a voice announcement ("system armed",
      etc.); +32 (-> 33/34/35) suppresses that spoken announcement.
    - OPT_SILENT_ARMDISARM silences the exit/entry-delay countdown (beeps) heard
      while arming and disarming.
    Both can be on for a fully silent arm/disarm; neither affects the siren.
    """
    if options.get(OPT_SILENT_STATUS) and state in _SETTLED_STATES:
        return True
    if options.get(OPT_SILENT_ARMDISARM) and state in _DELAY_STATES:
        return True
    return False


def indicator_for_state(state: str, options: dict) -> int | None:
    """Map an alarm_control_panel state to an Indicator value (or None to skip)."""
    if state == "triggered":
        value = int(options.get(OPT_TRIGGERED_SOUND, 4))
    else:
        opt = _STATE_OPTION.get(state)
        if opt is None:
            return None
        value = int(options.get(opt, -1))
        if _mute_sound(state, options) and 0 <= value < 2 * INDICATOR_SILENT_BIT:
            value += INDICATOR_SILENT_BIT
    if value < 0 or value > INDICATOR_MAX:
        return None
    return value
