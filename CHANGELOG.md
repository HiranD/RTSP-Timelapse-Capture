# Changelog

All notable changes to this project are documented in this file.

## [3.6.0] - 2026-07-25

### Changed
- **"Delete snapshots after creating video" moved to the Video Export tab, and now applies to every
  video.** It previously lived on the Scheduling tab but was only honoured by scheduled sessions and
  by videos created through the remote API — never by the Video Export tab's own Export button. That
  meant a setting on the scheduling page was silently deleting frames for people driving the app
  from NINA (who never open that tab, since the scheduler and the remote API are mutually
  exclusive), while not doing anything for the button most obviously associated with making a video.
  All three paths now honour it. Exports started from the Video Export tab **ask for confirmation
  first**; scheduled and remote renders don't, as they run unattended. Your existing setting is
  migrated automatically.

### Fixed
- The Video Export tab wrote its "last used output folder" to a stray `camera_config.json` in the
  working directory instead of the app's real config, so the folder never persisted after a manual
  export.

### Added
- **Session events and event overlays** ([#15](https://github.com/HiranD/RTSP-Timelapse-Capture/issues/15)).
  External programs can now tell the app what happened during the night, and have it show up on the
  timelapse:
  - **`POST /events`** on the Remote Control API records a timestamped event —
    `{"title": "Autofocus Complete", "detail": "HFR 2.31 -> 1.62", "category": "autofocus"}`.
    `GET /events` lists what the current session has recorded. No new port or setting: the existing
    **Integrations → Remote Control** toggle governs it. Events are accepted only while capture is
    running (there are no frames to attach them to otherwise); the endpoint returns **409** when
    stopped, which callers should treat as "skip" rather than an error.
  - Events are appended to **`events.jsonl`** in that night's snapshot folder, beside the frames
    they describe.
  - **Overlay session events** on the **Video Export** tab burns them into the video as captions at
    the point in the night they happened, holding for a configurable few seconds of finished video.
  - **Write events CSV** (also on the Video Export tab, and independent of the overlay) writes a
    **`<video-name>.events.csv`** next to the rendered video, with both the wall-clock time and the
    video timecode of each event — so a session can be lined up against the footage or imported
    into a video editor. Off by default. Note that `events.jsonl` sits inside the snapshot folder
    and is deleted with it when *Delete snapshots after video* is enabled, so with that on and this
    off a session's events are not retained anywhere.
  - See [`examples/README.md`](examples/README.md) for the endpoint reference and
    `examples/nina_send_event.ps1` for a ready-made sender.
  - The **RTSP Timelapse Control** NINA plugin (1.5.0+) sends these automatically: add its
    *Report Timelapse Events* trigger to a sequence and autofocus runs, filter changes, meridian
    flips, target changes and guiding loss are reported as they happen.

### Fixed
- **A UTF-8 BOM in `app_config.json` no longer wipes every setting.** Editing the config in
  Notepad, or writing it from PowerShell, prepends a byte-order mark; the loader read the file
  with the system locale encoding and failed on it, and because a failed load falls back to
  defaults the result was silent and total — camera, output folders and API port all appeared to
  reset themselves, and videos started landing in the app's working directory instead of the
  configured export folder. The file is now read as `utf-8-sig` (BOM tolerated) and written as
  plain UTF-8, which also stops non-ASCII paths being mangled on save.

## [3.5.0] - 2026-07-24

### Added
- **Start Now** on the Capture tab. The Capture Window now offers a **Start** choice — *At time*
  (wait until the Start Time, as before) or *Now* (begin capturing immediately). "Now" still
  auto-stops at the End Time, and **Stop** ends it early at any point. No more setting a Start Time
  in the past just to start right away. The choice is session-only and defaults to *At time*, so
  scheduled behavior is unchanged.
- **Reorganized Capture tab.** The single "Camera Configuration" box is split into three clearer
  groups — **Camera** (connection), **Capture Window** (when capture runs), and **Capture Settings**
  (how it captures) — so the schedule fields no longer sit under a "camera" heading.

### Fixed
- **Stream Path is finally used** ([#16](https://github.com/HiranD/RTSP-Timelapse-Capture/issues/16)).
  The RTSP URL was built with a hardcoded `/stream1` and the configured **Stream Path** was
  discarded, so every camera serving a different path — Hikvision `/Streaming/Channels/101`, Dahua
  `/cam/realmonitor?channel=1&subtype=0`, UniFi `/s0` — failed to connect no matter what you typed,
  in both **Test Connection** and **Start Capture**. The path is now used exactly as entered
  (query strings included); a blank field falls back to `/stream1`, and a missing leading slash is
  added for you.
- The URL is no longer mangled by a `?tcp` suffix, which turned a Dahua path into a doubled query
  string. It was never a real RTSP or FFmpeg option — transport is set by the FFmpeg options the app
  applies at startup, not by anything in the URL.
- The **Activity Log** now prints the stream URL being opened, with the password masked, for both
  Test Connection and Start Capture. A wrong path used to fail with no indication of what was
  actually dialled.
- A config file containing settings this version no longer has is no longer rejected outright.
  Previously one unknown key failed the entire load and silently reset every setting to defaults;
  unknown keys are now ignored and disappear on the next save.

### Removed
- The **Force TCP** checkbox (and its `camera.force_tcp` config key). It never switched transport —
  TCP is applied unconditionally to every connection through `OPENCV_FFMPEG_CAPTURE_OPTIONS` — so
  its only effect was appending the bogus `?tcp`. Behavior is unchanged: connections were always
  TCP, ticked or not. Existing config files load fine and the stale key is dropped automatically.

### Note when upgrading
If you previously typed a wrong Stream Path while troubleshooting a camera that also happens to
serve `/stream1`, that camera was connecting by accident and will now fail, because your setting is
finally being honored. The Activity Log shows the exact URL — correct the field, or clear it to fall
back to `/stream1`.

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
