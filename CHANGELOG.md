# Changelog

All notable changes to this project are documented in this file.

## [Unreleased] (v3.3.0)

### Added
- Discord webhook upload: automatically posts the generated timelapse video to a Discord
  channel after each night's session, with a configurable max upload size, optional auto
  quality reduction (re-encodes to fit the limit), and an export-resolution selector.
- Option to delete the generated video file after a successful Discord webhook upload.
  - Configurable in the Scheduling tab under Discord settings.
  - Config key: `astro_schedule.delete_video_after_discord_upload`.
- "Minimize to tray on startup" option: launches the app into the system tray for headless or
  always-running setups (config key `ui.minimize_to_tray_on_startup`).

## [3.2.1] - 2026-05-30
### Fixed
- Scheduler status label could get stuck on "Capturing" after a scheduled session ended; it now
  reflects the scheduler's real state via a corrected stop sequence and periodic refresh.

## [3.2.0] - 2026-05-29
- Initial changelog entry created from README version history.
