# Ring Alarm Keypad (1st Gen) for Home Assistant

Use a **Ring Alarm Keypad, 1st Gen** (4AK1S7 US / 4AK1E9 EU) paired to **Z-Wave JS** as a
keypad for any `alarm_control_panel` — Alarmo, Manual, or another alarm integration.

- Enter your PIN and press **Home**, **Away** or **Disarm** to control the alarm panel.
- The keypad's lights follow the panel: disarmed, armed home, armed away, arming, pending, triggered.
- Optional **silent status lights** and a choice of **two siren sounds**.

Two ways to use it — pick **one**, not both, or every keypress will be handled twice:

| | Blueprint | Integration |
|---|---|---|
| Install | Paste one YAML file | Copy a folder or install with HACS |
| Setup | Automation from blueprint + a Text helper | Add Integration → pick keypad and panel |
| Extras | — | Event entity on the keypad device, `set_indicator` service, options UI |

> The Gen 2 keypad uses a different protocol (Indicator v3). For it, see
> [allenporter/home-assistant-ring-keypad](https://github.com/allenporter/home-assistant-ring-keypad).

## Requirements

- Home Assistant with the **Z-Wave JS** integration, keypad included (S2 Access Control recommended).
- An alarm panel entity, e.g. from [Alarmo](https://github.com/nielsfaber/alarmo).

## Install: integration

**HACS:** HACS → ⋮ → Custom repositories → add this repo as *Integration* → install → restart.

**Manual:** copy `custom_components/ring_keypad_gen1/` into `/config/custom_components/`, then restart.

Then **Settings → Devices & services → Add integration → Ring Keypad (1st Gen)**, pick the keypad and the
alarm panel.

### Options (⋯ → Configure)

| Option | What it does |
|---|---|
| Silent status lights | Mode lights without keypad sounds (adds 32) |
| Alarm sound when triggered | 4 warbling siren · 20 pulsing siren · 36 lights only · off |
| Code buffer timeout | How long a code typed before a mode button stays valid |
| Indicator values | Per-state values, if your firmware differs |

### Actions

| Action | What it does |
|---|---|
| `ring_keypad_gen1.chime` | Plays the door chime (value 15 by default), then re-shows the alarm state after 3 s. Use it for "door opened" automations. |
| `ring_keypad_gen1.set_indicator` | Sends any raw Indicator value 0–63. |

```yaml
# Example: chime when the front door opens
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door
    to: "on"
actions:
  - action: ring_keypad_gen1.chime
    data:
      config_entry_id: <your Ring Keypad entry>
```

### Brightness

The blue "disarmed" shield is controlled by the keypad firmware and stays lit while plugged in —
no Indicator value keeps it off. To make the keypad less bright, lower **parameter 16**
(Reduced Battery Life LED Brightness) and **parameter 15** (Extended Battery Life LED Brightness),
and adjust **parameter 11** (ambient light level above which the key backlight turns off).
**Parameter 7 (Power Mode)** only seems to matter on battery power.

## Install: blueprint

Copy `blueprints/automation/ring/ring_keypad_gen1.yaml` to `/config/blueprints/automation/ring/`,
reload automations, create a **Text helper** (mode *password*, max length 10), then create an
automation from the blueprint.

## How the keypad talks

**Keypad → Home Assistant** (Entry Control CC 0x6F, `zwave_js_notification` events)

| event_type | Meaning |
|---|---|
| 0 | Caching (typing started) |
| 1 | Cached keys (code, after the key-cache size is reached or timeout) |
| 2 | Enter (code) |
| 3 | Disarm button |
| 5 | Away button |
| 6 | Home button |
| 25 | Cancel (X) |

The code arrives either **with** the mode-button event or in a 1/2 event **just before** it; both are handled.
A disarm is never sent without a code. Codes are never written to entity attributes or logs.

**Home Assistant → keypad** (Indicator CC 0x87, **version 1**, single value)

Mapped on a US 4AK1S7, firmware 2.16, Z-Wave JS 15.31:

| Value | Lights | Sound |
|---|---|---|
| 0 | Off | — |
| **1** | Right shield amber — **Armed Home** | quiet |
| **2** | Left shield amber — **Armed Away** | quiet |
| **3** | Bottom shield blue / blue ring — **Disarmed** | quiet |
| **4** | Full red ring — **Alarm** | warbling siren (~1.4–3 kHz) |
| 6–7 | Full red ring | quiet |
| **8** | Red ring blinking | beeps |
| 9–14 | No visible change | faint/none |
| **15** | Lights go dark while the chime plays, then return | **Door chime** |
| 16 | No change | — |
| **20** | Full red ring | pulsing ~930 Hz siren (alternate) |
| **23** | Partial red ring animation (countdown) | quiet |
| 24–27 | Red ring blinking / held | beeps |

Structure: **low 4 bits** choose the light pattern, **+16** selects an alternate sound set,
**+32** mutes sirens and beeps (same lights) but **not** the door chime, **64–255 are ignored**.
Arming (23) and Pending (8) defaults are best guesses — change them in options.

Configuration parameters 22–24 (language, audio files) from the EU technical manual do **not**
respond on US firmware 2.16.

## Tools

`tools_probe_script.yaml` is the Home Assistant script used to map the Indicator values
(sync flash, timed sweep, Logbook entries) — useful if your firmware behaves differently.

## Development

```bash
uv venv && uv pip install pytest-homeassistant-custom-component
.venv/bin/pytest
```
