# Handoff: Ring Alarm Keypad (1st Gen) ↔ Home Assistant integration

You are picking up work on a custom Home Assistant integration (`ring_keypad_gen1`) that turns a
**Ring Alarm Keypad, 1st Gen** paired to **Z-Wave JS** into a keypad for an **Alarmo**
`alarm_control_panel`. The code, tests, blueprint and README are in this repo. You have MCP / direct
access to the user's Home Assistant, so you can check live state, call actions and read logs instead
of guessing.

**Immediate problem to solve:** when Alarmo changes state (armed/disarmed), the keypad's lights do
**not** change. Keypad → Alarmo (PIN + mode button) has not been confirmed on the live system either.
Start with [Debugging the sync](#1-debug-the-alarmo--keypad-sync-current-bug).

---

## 2026-11-04 — Silent arm/disarm / voice-suppression option (v0.4.0)

Added to answer "arm and disarm the house and not have the voice spoken from the keypad."

**The spoken voice is built into Indicator values 1/2/3** (armed_home=1 / armed_away=2 / disarmed=3):
the keypad speaks a voice announcement ("system armed", "disarmed", etc.) on those settled states.
The **+32 silent bit (→ 33/34/35) suppresses that voice**. (An earlier draft of this note wrongly
claimed 1/2/3 were "already quiet / no spoken voice" — that was corrected per the user.) There is no
separate voice/audio *config parameter* on this US firmware (params 22–24 time out); the only sound
levers are Key Tone Volume (param 10, user set to 3), Siren Volume (param 12) and the Indicator CC.
+32 also mutes the countdown beeps and sirens, but **not** the door chime.

Change: the single `silent_status` toggle was split into two complementary options (both set +32,
both keep the lights, neither touches the siren):

- `silent_status` → scoped to the **settled** states (disarmed / armed_home / armed_away and their
  aliases). Relabeled "Silent armed/disarmed status". **This is the lever for the user's request:
  with it on, the controller sends 33/34/35 instead of 1/2/3, suppressing the spoken voice.**
  (Existing entries keep the key; this narrows its effect from "all status states" to "settled
  states only" — safe here, the live entry has it `false`.)
- `silent_armdisarm` (**new**, default `false`) → mutes the **exit/entry-delay countdown beeps**
  (`arming` 23 → 55, `pending` 8 → 40). Enable both for a fully silent arm/disarm.

Code path verified from source + unit tests (no live indicator sent): `silent_status` on →
`indicator_for_state` returns 1+32/2+32/3+32 = 33/34/35 for armed_home/armed_away/disarmed, sent via
`async_set_indicator`. Logic lives in `logic._mute_sound()` (pure). Files touched: `const.py`,
`logic.py`, `config_flow.py`, `strings.json`, `translations/en.json`, `README.md`, `manifest.json`
(0.3.3 → 0.4.0), and tests. **26 tests pass** (was 21) — `test_silent_status` asserts armed_home→33,
`test_logic` asserts disarmed→35/armed_away→34. Arm/disarm both directions was left unchanged and is
already working (entry `01M6GPAZBV3EK4W40SZP9JDWJ1` loaded, following `alarm_control_panel.alarmo`,
event entity firing).

**Open question the live test resolves:** whether +32 mutes the *spoken voice* specifically (not only
beeps). The probe table proved +32 mutes beeps/sirens; the user states 1/2/3 are the voice, so
33/34/35 should be silent — the live arm/disarm is the confirmation.

**Not yet deployed.** Live hardware test (keep **param 12 Siren Volume = 1**): deploy 0.4.0, set
option **`silent_status: true`**, then arm Away and disarm at the keypad and confirm **no spoken
voice** while the lights still change. Then also set `silent_armdisarm: true` and confirm the
exit/entry-delay countdown beeps are gone too.

---

## 2026-11-04 — v0.4.1: Silent mode corrected to +16 alternate sound set (hardware-validated)

**Hardware test proved +32 is a dud** — value 35 still spoke "disarmed" on the live keypad. The real
silent set is the **+16 alternate sound set**: sending 17 / 18 / 19 gives the exact same persistent
status lights with **no voice and no beep**. Transient animations and reverting to the stored light
are always silent; the keypad only speaks on the explicit 1/2/3 command.

| Feature | v0.4.0 (broken) | v0.4.1 (fixed) |
|---------|-----------------|----------------|
| Silent settled states | 33/34/35 (+32) | **17/18/19 (+16)** |
| Silent arming delay | 55 (23+32) | **39 (23+16)** |
| Silent pending delay | 40 (8+32) | **24 (8+16)** |

**Changes:**
- `const.py`: `INDICATOR_SILENT_BIT = 16` (was 32), added `OPT_SILENT_ARMDISARM` to defaults
- `logic.py`: mute condition `0 <= value < 2 * INDICATOR_SILENT_BIT` (allows +16 for values < 32)
- Tests updated to expect 17/18/19/39/24
- README: documented correct silent values
- manifest: version 0.4.1

All 26 tests pass. Deployed and reloaded on live HA (entry `01M6GPAZBV3EK4W40SZP9JDWJ1`). New option
`silent_armdisarm` appears in integration options (default `false`).

---

## Environment

| Item | Value |
|---|---|
| Home Assistant | Supervised install |
| Z-Wave stack | Z-Wave JS UI **11.25.1**, zwave-js **15.31.2**, HA `zwave_js` integration |
| Keypad | Ring Alarm Keypad 1st Gen, US **4AK1S7-0EN0**, firmware **2.16**, Z-Wave **node 26**, `0x0346 0x0101-0x0201`, S2 Access Control, FLiRS (1000 ms) |
| Alarm panel | Alarmo (likely `alarm_control_panel.alarmo` — **verify**; there may be per-area panels) |
| Hardware note | The keypad's USB power input was repaired: a cable is soldered to the `DC` / `GND1` pads. Polarity is verified (+5 V). If the keypad gets hot or the battery swells, stop and tell the user. |

## Security / privacy rules

- **Never log, print, store, commit or echo PIN codes.** Entry Control events carry codes in
  `event_data` in plain text. Z-Wave JS UI's event log and node JSON exports also contain them.
  Redact codes in anything you show or write.
- The event entity deliberately omits codes; keep it that way.
- Don't arm or disarm the real alarm, or set off sirens, without telling the user first. Siren
  volume is config param 12. Keep it at 1 while testing.

---

## Repo layout

```
custom_components/ring_keypad_gen1/
  __init__.py      setup/unload, actions: set_indicator, chime
  keypad.py        KeypadController: zwave_js_notification -> alarm actions; alarm state -> Indicator
  logic.py         pure logic (code buffering, state -> indicator value), unit-tested without HA
  config_flow.py   user step (keypad device + alarm entity), options flow
  event.py         Event entity on the keypad's existing Z-Wave device
  const.py         constants, defaults, findings
  strings.json / translations/en.json / services.yaml / manifest.json (v0.3.1)
tests/             pytest-homeassistant-custom-component tests (18 passing)
blueprints/automation/ring/ring_keypad_gen1.yaml   blueprint alternative (don't run both)
tools_probe_script.yaml                            HA script used to map Indicator values
README.md
```

Run the tests:

```bash
uv venv && uv pip install pytest-homeassistant-custom-component
.venv/bin/pytest -q
```

Tests pass against HA **2026.2.3**. They mock `zwave_js.set_value` and the `alarm_control_panel.*`
services, and add `zwave_js` to `hass.config.components` to satisfy the manifest dependency.

## How the integration works

- **Config entry data:** `keypad_device_id` (HA device id of the Z-Wave keypad), `alarm_entity_id`.
- **Keypad → alarm:** listens on the HA bus for `zwave_js_notification` events where `device_id`
  matches and `command_class == 111` (Entry Control). `logic.handle_entry_control` handles both ways
  the Gen 1 sends a code (see below), then calls `alarm_control_panel.alarm_disarm|arm_home|arm_away`
  on the configured entity. A disarm is never sent without a code.
- **Alarm → keypad:** `async_track_state_change_event` on the alarm entity, plus a push of the
  current state at startup (`async_at_started`). It maps the state with `logic.indicator_for_state` and
  calls `zwave_js.set_value` with `command_class: 135, property: "value", value: N`.
- **Options:** silent status (+32), triggered sound (4 / 20 / 36 / off), code buffer timeout, and
  per-state indicator values.
- **Actions:** `ring_keypad_gen1.set_indicator` (raw 0–63) and `ring_keypad_gen1.chime` (default 15, then
  re-shows the alarm state after 3 s).
- **Debug logging (v0.3.1):** logs the alarm state changes it sees and every indicator value it
  sends, and warns if the alarm entity doesn't exist.

---

## Device protocol (verified on the user's keypad)

### Keypad → HA: Entry Control CC (0x6F / 111), v1

`zwave_js_notification` event, `command_class: 111`:

| event_type | Label | Notes |
|---|---|---|
| 0 | Caching | typing started |
| 1 | Cached keys | `event_data` = code; sent when the key cache fills (keyCacheSize = 8) or times out |
| 2 | Enter | ✓ key; `event_data` = code if typed |
| 3 | Disarm all | |
| 5 | Away | |
| 6 | Home | |
| 25 | Cancel | X key; may carry partial digits |

The code arrives either **attached to the mode event** (`Home` with `event_data`) or as a separate
**Enter / Cached keys** event about 0.5 s **before** a mode event that has no data. Both patterns were
observed.

Other reports from the keypad: Notification CC: Home Security motion (proximity; **never fired in
testing**), Power Management (AC mains disconnected 2 / re-connected 3, battery charging 12), and
System software failure. Battery CC.

### HA → keypad: Indicator CC (0x87 / 135), **version 1**, single value 0–255

Mapped from video and audio of probe sweeps, with HA Logbook timestamps:

| Value | Lights | Sound |
|---|---|---|
| 0 | mode lights off | — |
| **1** | right shield amber (**Armed Home**) | **spoken voice** ("system armed", etc.); +32 → 33 is silent |
| **2** | left shield amber (**Armed Away**) | **spoken voice**; +32 → 34 is silent |
| **3** | bottom shield blue / blue ring (**Disarmed**) | **spoken voice** ("disarmed"); +32 → 35 is silent |
| **4** | full red ring (**Alarm**) | warbling siren, about 1.4–3 kHz |
| 6–7 | full red ring | quiet |
| 8 | red ring blinking | beeps (current *pending* default) |
| 9–14 | no visible change | faint or none |
| **15** | lights dark while the chime plays, then return | **door chime** |
| 16 | no change | — |
| **20** | full red ring | pulsing siren, about 930 Hz (alternate) |
| 23 | partial red ring animation (countdown) | quiet (current *arming* default) |
| 24–27 | red blinking or held | beeps |
| 32–63 | same lights as value − 32 | **silent** (but 47 = 15 + 32 still plays the chime) |
| 64–255 | ignored | — |

Structure: the **low 4 bits** pick the light pattern, **+16** picks an alternate sound set, **+32**
mutes the spoken voice, sirens and beeps (not the door chime), and **values ≥ 64 are ignored**.

**The blue "disarmed" bottom shield is firmware-controlled.** No tested value keeps it off (0, 15, 16
and 47 tested by hand). Param 7 (Power Mode) = 0 made no difference on mains power. A display-timeout
feature was tried and removed for this reason.

### Configuration parameters

Params 1–21 are defined in the Z-Wave JS device file (`/data/db/devices/0x0346/alarm_keypad_gen1.json`).
The ones that matter here:

| # | Name | Default | Notes |
|---|---|---|---|
| 6 | Status Change Timeout | 15 | 10–60 s |
| 7 | Power Mode | 0 | 0 Extended Battery Life, 1 Normal. Seems to apply on battery only. |
| 8 | Key Backlight Timeout | 3 | 1–15 s |
| 10 | Key Tone Volume | 8 | user set 3 |
| 11 | Ambient Light Sensor Level | 5 | backlight off above this |
| 12 | Siren Volume | 6 | **keep at 1 while testing** |
| 15 / 16 | LED brightness (Extended / Reduced battery life) | 50 / 65 | 0–100%; **0% not yet tested — may switch the blue shield off** |

The EU technical manual lists params **22 (Language), 23 (Supported languages, 4 bytes) and 24 (Audio
file info, 3 bytes)**. On this US firmware, Configuration Get for 22–24 **times out**, while param 12
answers in about 150 ms, so they aren't supported here.

---

## Tasks

### 1. Debug the Alarmo → keypad sync (current bug)

Use your HA access to find exactly where it breaks:

1. **Is v0.3.1 installed and loaded?** Check `/config/custom_components/ring_keypad_gen1/manifest.json`
   for version 0.3.1, and that a `ring_keypad_gen1` config entry exists and is `loaded`. If it's
   missing, install it, restart, and create the entry with the user.
2. **Is the old blueprint automation disabled?** It's named like "Ring Alarm Keypad (1st Gen)…" and
   uses the blueprint. Running both causes double handling.
3. **Compare the configured `alarm_entity_id` with the entity Alarmo actually changes.** List the
   `alarm_control_panel.*` entities and watch which one changes when the user arms. With Alarmo
   areas, there's one per area plus a master.
4. **Test the output path:** call `ring_keypad_gen1.set_indicator` with value `1` and ask the user
   whether the right shield turns amber. Or call `zwave_js.set_value` directly with
   `device_id`, `command_class: 135`, `property: value`, `value: 1`.
5. **Enable debug logging** for `custom_components.ring_keypad_gen1` (and `homeassistant.components.zwave_js`
   if needed). Change Alarmo's state and read the logs. Expect `… changed to armed_away`, then
   `Setting keypad … indicator to 2`. A warning means the send failed.
6. **Possible causes to check in the code:**
   - `async_track_state_change_event` is tied to the entity id captured at setup.
   - Alarmo may go through `arming` before `armed_*`, so the keypad shows 23 first. Confirm the final
     state is also sent.
   - The device id stored at setup may not be the current Z-Wave device id if the keypad was
     re-included. Check the device registry.
   - The keypad is FLiRS, so check for timeouts or dropped commands in the Z-Wave JS UI debug log.
7. Fix the bug, add a regression test, bump the version, and confirm on the live keypad with the user.

### 2. Confirm keypad → Alarmo on the live system

Have the user enter a code and press **Home / Away / Disarm**. Check that Alarmo changes state, and
that the event entity (`event.ring_keypad_keypad` or similar) records `alarm_arm_home`, etc.,
**without** a code in its attributes. Also test the wrong-code path: Alarmo should reject it, the
`action_failed` event should fire, and the keypad should show the real state again.

### 3. Remaining hardware tests (ask the user to watch the keypad)

- Params **16 = 0** and **15 = 0**: does the blue shield turn off, and do the Home, Away and alarm
  lights still show? If so, consider a night-dimming option.
- Values **61, 62, 63** (not swept), and **31** (15 + 16; possibly a second chime).
- Which of **8** and **23** suits Alarmo's *pending* (entry delay) and *arming* (exit delay).

### 4. Publishing (after it works)

- Replace the `example.com/REPLACE-with-your-repo` URLs in `manifest.json` and the blueprint's
  `source_url`. Add `codeowners`, a LICENSE (Apache-2.0 to match the Gen 2 project), and a GitHub
  Actions workflow running pytest and hassfest / HACS validation.
- Consider contributing Gen 1 support or findings to
  [allenporter/home-assistant-ring-keypad](https://github.com/allenporter/home-assistant-ring-keypad),
  which targets the Gen 2 (Indicator v3).
- Z-Wave JS device database PR for `packages/config/config/devices/0x0346/alarm_keypad_gen1.json`:
  fix the dead manual link (current manual:
  https://d1kusojqr3t85q.cloudfront.net/jrz4hnnvdyct/3D2s1xqVOjMZTQ8jHurfcQ/0c866741dfb0a18fa18884e5345bdccf/Keypad_Technical_Manual_1st_gen.pdf),
  set the minimum for params 17 and 18 to 1 (not 0), clarify the param 7 labels, add a note that
  params 22–24 don't respond on US firmware 2.16, and add Indicator notes.

## Working with the user

- They're comfortable with soldering, multimeters, HA, Z-Wave JS UI and Git. Keep explanations
  practical and short.
- They can film the keypad. The probe script `tools_probe_script.yaml` has a sync double-flash, a timed
  sweep, a specific-values list, siren volume control and Logbook entries for lining up video
  timestamps.
- Ask before anything irreversible: deleting config entries, excluding or re-including the keypad,
  factory reset, or changing Alarmo settings.
