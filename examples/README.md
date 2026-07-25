# Remote Control API — example scripts (NINA & others)

These scripts drive RTSP Timelapse Capture from an external program over its
local HTTP API. They're handy for **N.I.N.A.** ("Nighttime Imaging 'N'
Astronomy") via the **Advanced Sequencer → External Script** instruction, but
work with anything that can make an HTTP request (curl, PowerShell, Python …).

> **There's a native NINA plugin: RTSP Timelapse Control.** It drives this same
> API from inside NINA (start/stop, plus a scheduled timelapse that auto-stops
> and renders) — install it from <https://github.com/HiranD/nina-rtsp-timelapse>.
> The scripts below are the no-install alternative.

## 1. Enable the API

In the app: **Integrations** tab → **Remote Control** → tick **Enable remote
control API**. The default address is `http://127.0.0.1:8787`.

Notes:
- The server is **local-only** (bound to `127.0.0.1`) and has **no auth token** —
  only programs on this PC can reach it.
- It is **mutually exclusive** with **Enable automatic scheduling** (Scheduling
  tab). Turning one on greys out the other. Use the API when you want NINA (not
  the built-in scheduler) to decide when capture runs.
- Because the scheduler's automatic post-session video step won't run in this
  mode, the API exposes `/video/create` so you can trigger it yourself.

## 2. Endpoints

| Method | Path             | Purpose                                                        |
|--------|------------------|---------------------------------------------------------------|
| GET    | `/health`        | Liveness check → `{"ok": true, "version": "..."}`             |
| GET    | `/status`        | `{capturing, state, frame_count, uptime_seconds, last_error, scheduler_enabled, session_start_time}` |
| POST   | `/capture/start`    | Start capture                                               |
| POST   | `/capture/stop`     | Stop capture                                                |
| POST   | `/capture/schedule` | Start capture (if needed) and auto-stop at `stop_at`        |
| POST   | `/video/create`     | Create the timelapse video (newest session, or a given date) |
| POST   | `/events`           | Record a timestamped session event (see below)              |
| GET    | `/events`           | Events recorded during the current session                  |

`/capture/schedule` starts capture if it isn't already running and arms an
in-app timer that stops it at `stop_at` — and renders the session afterwards if
`create_video` is true — so the stop fires even if the external program never
sends a separate stop. Body:

```
{"stop_at": "20250620-233000", "create_video": true}
```

`stop_at` is `YYYYMMDD-HHMMSS` (local time) and must be in the future. This is
what the NINA plugin's "scheduled timelapse" uses.

`/video/create` accepts an optional JSON body. With no body it renders the most
recent capture folder; `date` targets a specific night and `since`
(`YYYYMMDD-HHMMSS`) keeps only frames captured at/after that time — so one session
renders cleanly even when several share a date folder:

```
{"date": "20250620", "since": "20250620-210000"}
```

Tip: read `session_start_time` from `/status` (the current/most-recent session's
start) and pass it back as `since` to render exactly that session.

It honours your **Video Export** preset and **Discord** upload settings.

### Session events

`POST /events` records what happened during the night — autofocus runs, meridian
flips, filter changes — so they can be shown on the finished timelapse and
exported as a log. Only `title` is required:

```
{"title": "Autofocus Complete", "detail": "HFR 2.31 -> 1.62",
 "category": "autofocus", "time": "20250620-230518",
 "data": {"hfr_before": 2.31, "hfr_after": 1.62}}
```

| Field | Notes |
|---|---|
| `title` | **Required.** The caption's first line. |
| `detail` | Optional second line, drawn smaller. |
| `category` | Optional grouping key, e.g. `autofocus`, `filter`, `target`. |
| `time` | Optional `YYYYMMDD-HHMMSS` (local). Defaults to now. |
| `data` | Optional object of structured values — written to the log, never drawn. |

**Events are only accepted while capture is running** — otherwise there are no
frames to attach them to. When capture is stopped the endpoint returns **409**,
which callers should treat as "skip", not as a failure worth aborting a sequence
over. Other problems (no `title`, an unparseable `time`) return 400.

Events are appended to `events.jsonl` inside that night's snapshot folder, next
to the frames they describe.

To see them on the video, tick **Overlay session events** on the **Video Export**
tab; each caption holds for a few seconds of finished video at the point in the
night it happened. Either way — captions on or off — a
`<video-name>.events.csv` is written next to the rendered video with both the
wall-clock time and the video timecode of each event, so the log can be lined up
against the footage or imported into a video editor.

## 3. Files here

| File                     | What it does                                              |
|--------------------------|----------------------------------------------------------|
| `nina_start.bat`         | `POST /capture/start` (curl)                              |
| `nina_stop.bat`          | `POST /capture/stop` (curl)                               |
| `nina_create_video.bat`  | `POST /video/create` for the newest session (curl)       |
| `nina_capture.ps1`       | PowerShell variant: `start` / `stop` / `video` / `status`|
| `nina_send_event.ps1`    | `POST /events` — send a session event/marker              |

`curl.exe` ships with Windows 10/11, so the `.bat` files need no extra install.
If you changed the port, edit it in each script.

## 4. Using them in NINA

In a sequence, add an **External Script** instruction and point it at the script:

- **At sequence start:** `nina_start.bat`
- **At sequence end:** `nina_stop.bat`
- **After stop (optional):** `nina_create_video.bat`

The `.bat` files use `curl -f`, so a failed request returns a non-zero exit code
that NINA can detect.

To mark events on the timelapse, add **External Script** instructions where they
matter in the sequence:

```
powershell -File nina_send_event.ps1 -Title "Target: M31" -Category target
powershell -File nina_send_event.ps1 -Title "Meridian Flip" -Category mount
```

`nina_send_event.ps1` exits 0 when capture isn't running (the 409 case), so a
marker placed before capture starts won't abort the sequence.

## 5. Quick manual test

```bat
curl http://127.0.0.1:8787/status
curl -X POST http://127.0.0.1:8787/capture/start
curl -X POST -H "Content-Type: application/json" ^
     -d "{\"title\":\"Test Event\",\"detail\":\"hello\"}" ^
     http://127.0.0.1:8787/events
curl http://127.0.0.1:8787/events
curl -X POST http://127.0.0.1:8787/capture/stop
```
