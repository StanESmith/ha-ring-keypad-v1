"""Unit tests for the HA-independent keypad logic."""

from custom_components.ring_keypad_gen1.const import (
    DEFAULT_OPTIONS,
    OPT_SILENT_STATUS,
    OPT_TRIGGERED_SOUND,
)
from custom_components.ring_keypad_gen1.logic import (
    ACTION_ARM_AWAY,
    ACTION_ARM_HOME,
    ACTION_DISARM,
    CodeBuffer,
    handle_entry_control,
    indicator_for_state,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def make_buffer(max_age: float = 10):
    clock = FakeClock()
    return CodeBuffer(max_age=max_age, clock=clock), clock


def test_code_attached_to_mode_button():
    buf, _ = make_buffer()
    act = handle_entry_control(buf, 6, "1234")
    assert act.action == ACTION_ARM_HOME and act.code == "1234"


def test_code_sent_before_mode_button():
    buf, clock = make_buffer()
    assert handle_entry_control(buf, 2, "1234") is None  # Enter with code
    clock.t = 0.6
    act = handle_entry_control(buf, 3, None)  # Disarm, no data
    assert act.action == ACTION_DISARM and act.code == "1234"


def test_cached_keys_then_away():
    buf, clock = make_buffer()
    handle_entry_control(buf, 1, "98765432")
    clock.t = 2
    act = handle_entry_control(buf, 5, "")
    assert act.action == ACTION_ARM_AWAY and act.code == "98765432"


def test_stale_code_is_not_used():
    buf, clock = make_buffer(max_age=10)
    handle_entry_control(buf, 2, "1234")
    clock.t = 11
    assert handle_entry_control(buf, 3, None) is None  # disarm without code is refused
    act = handle_entry_control(buf, 6, None)
    assert act.action == ACTION_ARM_HOME and act.code is None


def test_code_used_only_once():
    buf, clock = make_buffer()
    handle_entry_control(buf, 2, "1234")
    assert handle_entry_control(buf, 3, None).code == "1234"
    assert handle_entry_control(buf, 3, None) is None


def test_cancel_clears_buffer():
    buf, _ = make_buffer()
    handle_entry_control(buf, 2, "1234")
    handle_entry_control(buf, 25, None)
    assert handle_entry_control(buf, 3, None) is None


def test_ignores_caching_and_unknown_events():
    buf, _ = make_buffer()
    assert handle_entry_control(buf, 0, None) is None
    assert handle_entry_control(buf, 99, "1") is None


def test_indicator_defaults():
    o = dict(DEFAULT_OPTIONS)
    assert indicator_for_state("disarmed", o) == 3
    assert indicator_for_state("armed_home", o) == 1
    assert indicator_for_state("armed_night", o) == 1
    assert indicator_for_state("armed_away", o) == 2
    assert indicator_for_state("armed_vacation", o) == 2
    assert indicator_for_state("arming", o) == 23
    assert indicator_for_state("pending", o) == 8
    assert indicator_for_state("triggered", o) == 4
    assert indicator_for_state("unknown", o) is None


def test_indicator_silent_and_alarm_sound():
    o = {**DEFAULT_OPTIONS, OPT_SILENT_STATUS: True, OPT_TRIGGERED_SOUND: "20"}
    assert indicator_for_state("disarmed", o) == 35
    assert indicator_for_state("armed_away", o) == 34
    assert indicator_for_state("triggered", o) == 20  # alarm sound not muted
    o[OPT_TRIGGERED_SOUND] = "-1"
    assert indicator_for_state("triggered", o) is None
