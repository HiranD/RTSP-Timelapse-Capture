# Changelog

All notable changes to this project are documented in this file.

## [3.4.0] - 2026-06-28

### Added
- **Remote Control HTTP API** (opt-in, localhost-only) so external software (e.g. **N.I.N.A.**) can
  drive capture — enable it on the Integrations tab → Remote Control. Bound to `127.0.0.1` with no
  auth token; mutually exclusive with automatic scheduling (enforced in the UI). Endpoints:
  `GET /health`, `GET /status`, `POST /capture/start`, `POST /capture/stop`,
  `POST /capture/schedule`, `POST /video/create`.
- **`/capture/schedule`** — starts capture if needed and arms an app-owned timer that auto-stops at
  a given time (and optionally renders the video), so the stop fires regardless of the external
  sequence.
- **`/video/create`** — trigger video creation for the newest or a given session, with an optional
  `since` filter so one session renders cleanly when several share a date folder.
- **`/status`** exposes `session_start_time` so a client can render exactly the current/most-recent
  session (read it, pass it back as `since`).
- Ready-to-use NINA example scripts (`.bat` + a PowerShell variant) bundled under `examples/`, with
  setup steps in `examples/README.md`.

## [3.3.0] - 2026-06-20

### Added
- New **Integrations** tab consolidating optional, set-once integrations and unattended-operation
  options (Discord upload + application/startup options), with hover tooltips on every control.
- Discord webhook upload: automatically posts the generated timelapse video to a Discord
  channel after each night's session, with a configurable max upload size, optional auto
  quality reduction (re-encodes to fit the limit), and an export-resolution selector.
- Option to delete the generated video file after a successful Discord webhook upload.
  - Configurable on the Integrations tab under Discord Upload.
  - Config key: `astro_schedule.delete_video_after_discord_upload`.
- Option to keep the re-encoded copy that was uploaded to Discord — saved as a date-stamped file
  inside the `.discord_encode` folder instead of being deleted (config key
  `astro_schedule.discord_keep_reencoded`).
- **Minimize to tray** option (Integrations tab): hides the window to the system tray instead of the
  taskbar — the app can start minimized in the tray on launch, and the minimize button also sends it
  there (config key `ui.minimize_to_tray`).
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
