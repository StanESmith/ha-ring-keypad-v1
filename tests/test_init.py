"""Integration tests: config flow, keypad -> alarm, alarm -> keypad."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.ring_keypad_gen1.const import (
    CONF_ALARM_ENTITY,
    CONF_KEYPAD_DEVICE,
    DEFAULT_OPTIONS,
    DOMAIN,
    OPT_SILENT_ARMDISARM,
    OPT_SILENT_STATUS,
)

ALARM = "alarm_control_panel.house"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def keypad_device(hass: HomeAssistant) -> str:
    """A fake Z-Wave JS device for the keypad (zwave_js itself is not loaded)."""
    hass.config.components.add("zwave_js")  # satisfy the manifest dependency
    zw_entry = MockConfigEntry(domain="zwave_js")
    zw_entry.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=zw_entry.entry_id,
        identifiers={("zwave_js", "1234-26")},
        manufacturer="Ring",
        model="4AK1S7-0EN0 / 4AK1E9-0EU0",
        name="Ring Keypad",
    )
    return dev.id


async def _setup(hass, keypad_device, options=None):
    hass.states.async_set(ALARM, "disarmed")
    set_value = async_mock_service(hass, "zwave_js", "set_value")
    calls = {
        s: async_mock_service(hass, "alarm_control_panel", s)
        for s in ("alarm_disarm", "alarm_arm_home", "alarm_arm_away")
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_KEYPAD_DEVICE: keypad_device, CONF_ALARM_ENTITY: ALARM},
        options={**DEFAULT_OPTIONS, **(options or {})},
        unique_id=keypad_device,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, set_value, calls


def _ec(hass, device_id, event_type, data=None):
    hass.bus.async_fire(
        "zwave_js_notification",
        {
            "device_id": device_id,
            "command_class": 111,
            "event_type": event_type,
            "event_data": data,
        },
    )


async def test_config_flow(hass: HomeAssistant, keypad_device):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    hass.states.async_set(ALARM, "disarmed")
    async_mock_service(hass, "zwave_js", "set_value")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_KEYPAD_DEVICE: keypad_device, CONF_ALARM_ENTITY: ALARM}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ring Keypad"
    assert result["options"] == DEFAULT_OPTIONS


async def test_state_pushed_on_start_and_change(hass: HomeAssistant, keypad_device):
    _, set_value, _ = await _setup(hass, keypad_device)
    assert set_value[-1].data["value"] == 3  # current state pushed at startup
    assert set_value[-1].data["command_class"] == 135
    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 2
    hass.states.async_set(ALARM, "triggered")
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 4


async def test_silent_status(hass: HomeAssistant, keypad_device):
    _, set_value, _ = await _setup(hass, keypad_device, {OPT_SILENT_STATUS: True})
    hass.states.async_set(ALARM, "armed_home")
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 33


async def test_silent_armdisarm_mutes_delay_countdown(
    hass: HomeAssistant, keypad_device
):
    _, set_value, _ = await _setup(hass, keypad_device, {OPT_SILENT_ARMDISARM: True})
    hass.states.async_set(ALARM, "arming")
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 55  # 23 + 32, exit-delay beeps muted
    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 2  # settled state untouched


async def test_keypad_disarm_with_separate_code(hass: HomeAssistant, keypad_device):
    _, _, calls = await _setup(hass, keypad_device)
    _ec(hass, keypad_device, 2, "1234")
    _ec(hass, keypad_device, 3, None)
    await hass.async_block_till_done()
    assert calls["alarm_disarm"][-1].data == {
        "entity_id": [ALARM],
        "code": "1234",
    } or calls["alarm_disarm"][-1].data == {"entity_id": ALARM, "code": "1234"}


async def test_keypad_ignores_other_devices_and_codeless_disarm(
    hass: HomeAssistant, keypad_device
):
    _, _, calls = await _setup(hass, keypad_device)
    _ec(hass, "someone-else", 6, "1234")
    _ec(hass, keypad_device, 3, None)
    await hass.async_block_till_done()
    assert not calls["alarm_arm_home"] and not calls["alarm_disarm"]


async def test_event_entity_fires_without_code(hass: HomeAssistant, keypad_device):
    await _setup(hass, keypad_device)
    _ec(hass, keypad_device, 6, "1234")
    await hass.async_block_till_done()
    states = hass.states.async_all("event")
    assert len(states) == 1
    st = states[0]
    assert st.attributes["event_type"] == "alarm_arm_home"
    assert "1234" not in str(st.attributes)


async def test_unload(hass: HomeAssistant, keypad_device):
    entry, set_value, _ = await _setup(hass, keypad_device)
    assert await hass.config_entries.async_unload(entry.entry_id)
    n = len(set_value)
    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    assert len(set_value) == n


async def test_chime_then_restores_state(hass: HomeAssistant, keypad_device):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    entry, set_value, _ = await _setup(hass, keypad_device)
    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "chime", {"config_entry_id": entry.entry_id}, blocking=True
    )
    assert set_value[-1].data["value"] == 15  # door chime by default
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert set_value[-1].data["value"] == 2  # armed away shown again


async def test_set_indicator_service_validates(hass: HomeAssistant, keypad_device):
    from homeassistant.exceptions import ServiceValidationError

    entry, set_value, _ = await _setup(hass, keypad_device)
    await hass.services.async_call(
        DOMAIN,
        "set_indicator",
        {"config_entry_id": entry.entry_id, "value": 33},
        blocking=True,
    )
    assert set_value[-1].data["value"] == 33
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "chime", {"config_entry_id": "nope"}, blocking=True
        )


async def test_works_when_entry_points_at_a_duplicate_device(
    hass: HomeAssistant, keypad_device
):
    """A second registry device shares the node's identifiers but belongs to
    another config entry (what the event entity used to create). Z-Wave JS
    reports events under, and accepts commands for, its own device only."""
    other = MockConfigEntry(domain="light")
    other.add_to_hass(hass)
    ghost = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("zwave_js", "1234-26")},
        name="Ring Keypad",
    )
    if ghost.id == keypad_device:
        # Older Home Assistant merges devices by identifier; build the split by hand
        # (newer versions keep one device per config entry).
        ghost = dr.DeviceEntry(id="ghost-device-id", identifiers={("zwave_js", "1234-26")})
        dr.async_get(hass).devices["ghost-device-id"] = ghost
    entry, set_value, calls = await _setup(hass, ghost.id)

    _ec(hass, keypad_device, 6, "1234")  # events arrive under the real device id
    await hass.async_block_till_done()
    assert calls["alarm_arm_home"]

    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    assert set_value[-1].data["device_id"] == keypad_device  # commands go there too


async def test_event_entity_linked_to_zwave_device_without_new_device(
    hass: HomeAssistant, keypad_device
):
    await _setup(hass, keypad_device)
    reg = dr.async_get(hass)
    assert len([d for d in reg.devices.values() if d.name == "Ring Keypad"]) == 1
    ent = er.async_get(hass).async_get("event.ring_keypad_keypad")
    assert ent is not None and ent.device_id == keypad_device


async def test_state_resent_when_node_comes_back_alive(
    hass: HomeAssistant, keypad_device
):
    zw_entry = hass.config_entries.async_entries("zwave_js")[0]
    status = er.async_get(hass).async_get_or_create(
        "sensor",
        "zwave_js",
        "1234-26-nodeStatus",
        suggested_object_id="ring_keypad_node_status",
        device_id=keypad_device,
        config_entry=zw_entry,
    )
    hass.states.async_set(status.entity_id, "alive")
    _, set_value, _ = await _setup(hass, keypad_device)
    hass.states.async_set(ALARM, "armed_away")
    await hass.async_block_till_done()
    sent = len(set_value)

    hass.states.async_set(status.entity_id, "dead")
    await hass.async_block_till_done()
    assert len(set_value) == sent  # nothing to send while it is down

    hass.states.async_set(status.entity_id, "alive")
    await hass.async_block_till_done()
    assert len(set_value) == sent + 1
    assert set_value[-1].data["value"] == 2  # armed away shown again
