# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Changed
- Generalized "Minimize to tray on startup" into a single **Minimize to tray** option: when enabled,
  the minimize button now also hides the window to the tray (not only at startup). Renamed the config
  key `ui.minimize_to_tray_on_startup` → `ui.minimize_to_tray` (existing configs migrate automatically).

## [3.3.0] - 2026-06-19

### Added
- New **Integrations** tab consolidating optional, set-once integrations and unattended-operation
  options (Discord upload + application/startup options), with hover tooltips on every control.
- Discord webhook upload: automatically posts the generated timelapse video to a Discord
  channel after each night's session, with a configurable max upload size, optional auto
  quality reduction (re-encodes to fit the limit), and an export-resolution selector.
- Option to delete the generated video file after a successful Discord webhook upload.
  - Configurable on the Integrations tab under Discord Upload.
  - Config key: `astro_schedule.delete_video_after_discord_upload`.
- "Minimize to tray on startup" option: launches the app into the system tray for headless or
  always-running setups (config key `ui.minimize_to_tray_on_startup`).
- Custom application icon (`assets/icon.svg`) for the window, taskbar, tray, and executable, with a
  build script (`scripts/build_icon.py`) to regenerate `icon.ico`/`icon.png` from the SVG.

### Changed
- "Start automatically when Windows starts" (added in v3.2.0) moved from the Scheduling tab to the
  new Integrations tab.

## [3.2.1] - 2026-05-30
### Fixed
- Scheduler status label could get stuck on "Capturing" after a scheduled session ended; it now
  reflects the scheduler's real state via a corrected stop sequence and periodic refresh.

## [3.2.0] - 2026-05-29
- Initial changelog entry created from README version history.
