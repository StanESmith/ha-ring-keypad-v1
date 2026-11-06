[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]

[![Add to Home Assistant][add-to-ha-shield]][add-to-ha-url]

# Ring Alarm Keypad (1st Gen)

Use a **Ring Alarm Keypad, 1st Gen** (US 4AK1S7 / EU 4AK1E9) paired to **Z-Wave JS** as a keypad for any `alarm_control_panel` — [Alarmo](https://github.com/nielsfaber/alarmo), [Manual Alarm](https://www.home-assistant.io/integrations/manual/), or another alarm integration.

- Enter your PIN and press **Home**, **Away** or **Disarm** to control the alarm panel.
- The keypad's lights follow the panel: disarmed, armed home, armed away, arming, pending, triggered.
- Optional **silent status lights** (no spoken voice) and **silent arm/disarm** (no countdown beeps).
- Choice of **two siren sounds** or lights-only when triggered.

> **Gen 2 keypad?** It uses a different protocol (Indicator v3). See [allenporter/home-assistant-ring-keypad](https://github.com/allenporter/home-assistant-ring-keypad).

| Feature | Description |
|---------|-------------|
| **PIN entry** | Type code → press Home / Away / Disarm |
| **Status lights** | Keypad mirrors alarm panel state |
| **Silent status** | Suppresses spoken "system armed/disarmed" voice (uses +16 alternate sound set: 17/18/19) |
| **Silent arm/disarm** | Mutes exit/entry delay countdown beeps (arming 23→39, pending 8→24) |
| **Siren selection** | Warbling (4), pulsing (20), lights only (36), or off |
| **Chime action** | Play door chime via automation |
| **Event entity** | Keypad actions as Home Assistant events (no codes exposed) |
| **Raw indicator** | `set_indicator` service for custom values 0–63 |

---

## Requirements

- Home Assistant with **Z-Wave JS** integration, keypad included (S2 Access Control recommended)
- An alarm panel entity (e.g. Alarmo, Manual Alarm)

---

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.][hacs-add-repo-shield]][hacs-add-repo-url]

1. HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add this repository URL, category **Integration**
3. Search **Ring Keypad (1st Gen)** → **Download** → **Restart Home Assistant**
4. Settings → Devices & Services → **Add Integration** → **Ring Keypad (1st Gen)**
5. Select your keypad device and alarm panel entity

### Manual

```bash
# Copy to your config directory
cp -r custom_components/ring_keypad_gen1 /config/custom_components/
# Restart Home Assistant
```

---

## Configuration

After adding the integration, go to **Settings → Devices & Services → Ring Keypad (1st Gen) → Configure**:

| Option | Description | Default |
|--------|-------------|---------|
| **Silent armed/disarmed status** | Suppress spoken voice on settled states (disarmed/armed_home/armed_away) — uses +16 (17/18/19) | `false` |
| **Silent arm/disarm** | Mute exit/entry delay countdown beeps (arming/pending) — uses +16 (39/24) | `false` |
| **Alarm sound when triggered** | Warbling siren (4) · Pulsing siren (20) · Lights only (36) · Off | `4` |
| **Code buffer timeout** | Seconds a typed code stays valid before a mode button | `10` |
| **Indicator values** | Per-state Indicator values if your firmware differs | see below |

**Default Indicator values:**
| State | Value | Lights |
|-------|-------|--------|
| Disarmed | 3 | Blue bottom shield |
| Armed Home | 1 | Right amber shield |
| Armed Away | 2 | Left amber shield |
| Arming (exit delay) | 23 | Red count-up ring |
| Pending (entry delay) | 8 | Red blinking ring |

> **How silencing works:** The keypad speaks a voice announcement on values 1/2/3. The **+16 alternate sound set** (17/18/19) shows the same persistent lights **silently** (no voice, no beep). This is hardware-verified on US firmware 2.16. The +32 bit does **not** mute the voice on this firmware.

---

## Actions

| Action | Description |
|--------|-------------|
| `ring_keypad_gen1.chime` | Plays door chime (value 15), restores alarm state after 3 s |
| `ring_keypad_gen1.set_indicator` | Sends any raw Indicator value 0–63 |

**Example: chime when front door opens**

```yaml
automation:
  - trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - action: ring_keypad_gen1.chime
        data:
          config_entry_id: <your Ring Keypad entry>
```

---

## Brightness

The blue "disarmed" shield is firmware-controlled and stays lit on USB power — no Indicator value keeps it off. To dim:

- Lower **parameter 16** (Reduced Battery Life LED Brightness)
- Lower **parameter 15** (Extended Battery Life LED Brightness)
- Adjust **parameter 11** (ambient light level for key backlight off)
- **Parameter 7 (Power Mode)** only applies on battery power

---

## Protocol Details

### Keypad → Home Assistant (Entry Control CC 0x6F)

`zwave_js_notification` events with `command_class: 111`:

| Event Type | Label | Notes |
|------------|-------|-------|
| 0 | Caching | Typing started |
| 1 | Cached keys | Code (after cache fills or timeout) |
| 2 | Enter | Code |
| 3 | Disarm | |
| 5 | Away | |
| 6 | Home | |
| 25 | Cancel | X key |

Codes arrive either **with** the mode event or in a 1/2 event **just before** it; both patterns are handled. Disarm is never sent without a code. Codes are never logged or written to entity attributes.

### Home Assistant → Keypad (Indicator CC 0x87, v1)

Mapped on US 4AK1S7, firmware 2.16, Z-Wave JS 15.31:

| Value | Lights | Sound |
|-------|--------|-------|
| 0 | Off | — |
| **1** | Right shield amber — **Armed Home** | spoken voice |
| **2** | Left shield amber — **Armed Away** | spoken voice |
| **3** | Bottom shield blue / ring — **Disarmed** | spoken voice |
| **4** | Full red ring — **Alarm** | warbling siren (~1.4–3 kHz) ⚠️ |
| 6–7 | Full red ring | quiet |
| **8** | Red ring blinking | beeps |
| 9–14 | No visible change | faint/none |
| **15** | Dark during chime, then return | **Door chime** |
| 16 | No change | — |
| **20** | Full red ring | pulsing ~930 Hz siren |
| **23** | Partial red ring animation (countdown) | quiet |
| 24–27 | Red blinking/held | beeps |
| **17/18/19** | Same as 1/2/3 | **Silent** (no voice, no beep) |
| **39/24** | Same as 23/8 | **Silent** |
| 32–63 | Same as value−32 | Silent (except 47 = chime) |
| 64–255 | Ignored | — |

**Structure:** low 4 bits = light pattern, **+16** = alternate sound set (silent status), **+32** = mute (voice/sirens/beeps, not chime), **≥64 ignored**.

Configuration parameters 22–24 (language, audio files) from the EU manual **do not respond** on US firmware 2.16.

---

## Tools

`tools_probe_script.yaml` — Home Assistant script used to map Indicator values (sync flash, timed sweep, specific values, Logbook entries). Useful if your firmware behaves differently.

---

## Development

```bash
# Set up test environment
uv venv && uv pip install pytest-homeassistant-custom-component

# Run tests
.venv/bin/pytest
```

Tests run against Home Assistant 2026.2+ and mock `zwave_js.set_value` / `alarm_control_panel.*` services.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (`.venv/bin/pytest`)
5. Open a Pull Request

---

## License

Apache-2.0 — see [LICENSE](LICENSE)

---

## Attribution

This integration was built with the help of **Claude Code** (Anthropic).

---

## Links

- **Repository:** [github.com/StanESmith/ha-ring-keypad-v1](https://github.com/StanESmith/ha-ring-keypad-v1)
- **HACS:** Add as custom repository (Integration category)
- **Gen 2 integration:** [allenporter/home-assistant-ring-keypad](https://github.com/allenporter/home-assistant-ring-keypad)
- **Alarmo:** [nielsfaber/alarmo](https://github.com/nielsfaber/alarmo)

---

[releases-shield]: https://img.shields.io/github/v/release/StanESmith/ha-ring-keypad-v1?style=for-the-badge
[releases]: https://github.com/StanESmith/ha-ring-keypad-v1/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/StanESmith/ha-ring-keypad-v1?style=for-the-badge
[commits]: https://github.com/StanESmith/ha-ring-keypad-v1/commits/main
[license-shield]: https://img.shields.io/github/license/StanESmith/ha-ring-keypad-v1?style=for-the-badge
[license]: LICENSE
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://hacs.xyz/docs/faq/custom_repositories/
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026?style=for-the-badge
[buymecoffee-shield]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/StanESmith

[add-to-ha-shield]: https://my.home-assistant.io/badges/hacs_repository.svg
[add-to-ha-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=StanESmith&repository=ha-ring-keypad-v1&category=integration

[hacs-add-repo-shield]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-add-repo-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=StanESmith&repository=ha-ring-keypad-v1&category=integration