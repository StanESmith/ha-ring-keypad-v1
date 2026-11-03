"""Constants for the Ring Keypad (1st Gen) integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ring_keypad_gen1"

CONF_KEYPAD_DEVICE: Final = "keypad_device_id"
CONF_ALARM_ENTITY: Final = "alarm_entity_id"

OPT_CODE_TIMEOUT: Final = "code_timeout"
OPT_SILENT_STATUS: Final = "silent_status"
OPT_TRIGGERED_SOUND: Final = "triggered_sound"
OPT_IND_DISARMED: Final = "ind_disarmed"
OPT_IND_ARMED_HOME: Final = "ind_armed_home"
OPT_IND_ARMED_AWAY: Final = "ind_armed_away"
OPT_IND_ARMING: Final = "ind_arming"
OPT_IND_PENDING: Final = "ind_pending"

DEFAULT_CODE_TIMEOUT: Final = 10
DEFAULT_OPTIONS: Final[dict[str, int | bool | str]] = {
    OPT_CODE_TIMEOUT: DEFAULT_CODE_TIMEOUT,
    OPT_SILENT_STATUS: False,
    OPT_TRIGGERED_SOUND: "4",
    OPT_IND_DISARMED: 3,
    OPT_IND_ARMED_HOME: 1,
    OPT_IND_ARMED_AWAY: 2,
    OPT_IND_ARMING: 23,
    OPT_IND_PENDING: 8,
}

# Z-Wave command classes
CC_ENTRY_CONTROL: Final = 111
CC_INDICATOR: Final = 135

# Entry Control event types reported by the Gen 1 keypad
EC_CACHING: Final = 0
EC_CACHED_KEYS: Final = 1
EC_ENTER: Final = 2
EC_DISARM: Final = 3
EC_AWAY: Final = 5
EC_HOME: Final = 6
EC_CANCEL: Final = 25

# Indicator value structure (mapped on a US 4AK1S7, firmware 2.16):
# low 4 bits select the light pattern, +16 selects the alternate sound set,
# +32 mutes sound, 64-255 are ignored by the keypad.
INDICATOR_SILENT_BIT: Final = 32
INDICATOR_MAX: Final = 63

TRIGGERED_SOUND_OPTIONS: Final = ["4", "20", "36", "-1"]
# Chimes. 15 = Ring "door open" chime (47 = 15 + 32 chimes too; +32 does not
# mute chimes). The blue "disarmed" shield goes dark only while a chime plays;
# it is firmware-controlled and no tested value keeps it off (0, 15, 16, 47).
CHIME_DOOR: Final = 15
CHIME_RESTORE_DELAY: Final = 3  # seconds before the alarm state is re-shown

# Event entity event types
EVENT_DISARM: Final = "alarm_disarm"
EVENT_ARM_HOME: Final = "alarm_arm_home"
EVENT_ARM_AWAY: Final = "alarm_arm_away"
EVENT_CODE_ENTERED: Final = "code_entered"
EVENT_CANCEL: Final = "code_cancel"
EVENT_ACTION_FAILED: Final = "action_failed"
EVENT_TYPES: Final = [
    EVENT_DISARM,
    EVENT_ARM_HOME,
    EVENT_ARM_AWAY,
    EVENT_CODE_ENTERED,
    EVENT_CANCEL,
    EVENT_ACTION_FAILED,
]

SIGNAL_KEYPAD_EVENT: Final = f"{DOMAIN}_keypad_event_{{}}"
