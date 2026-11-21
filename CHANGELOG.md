# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.5.0] - 2026-11-21

### Added

- Diagnostics download (the keypad's device id is left out; the typed code is never included).
- Tests for the options form, the actions and the diagnostics.
- Release workflow: pushing a `vX.Y.Z` tag runs the tests and publishes a GitHub release from this file.
- Brand icons, and the manifest category.

### Changed

- The "Alarm sound when triggered" option's "Off" choice is stored as `none` (older versions stored `-1`; both still work and an existing setting is kept).
- CI uses the current HACS validation action and the license file is the standard Apache 2.0 text.

## [0.4.1] - 2026-11-05

### Fixed

- Silent mode uses the +16 alternate sound set (17, 18, 19, 39, 24), which is what actually silences the keypad's voice on US firmware 2.16.

## [0.4.0] - 2026-11-04

### Added

- Silent armed/disarmed status and silent arm/disarm options, which suppress the keypad's spoken announcements and countdown beeps.

## [0.3.3] - 2026-11-03

First version kept in this repository: the keypad arms, disarms and cancels any `alarm_control_panel` with a typed code and the mode buttons, shows the panel's state on its lights, and offers the `set_indicator` and `chime` actions and a keypad event entity.
