# Remote Control API — example scripts (NINA & others)

These scripts drive RTSP Timelapse Capture from an external program over its
local HTTP API. They're handy for **N.I.N.A.** ("Nighttime Imaging 'N'
Astronomy") via the **Advanced Sequencer → External Script** instruction, but
work with anything that can make an HTTP request (curl, PowerShell, Python …).

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
| GET    | `/status`        | `{capturing, state, frame_count, uptime_seconds, last_error, scheduler_enabled}` |
| POST   | `/capture/start` | Start capture                                                  |
| POST   | `/capture/stop`  | Stop capture                                                   |
| POST   | `/video/create`  | Create the timelapse video (newest session, or a given date)  |

`/video/create` accepts an optional JSON body to target a specific night;
otherwise it uses the most recent capture folder:

```
{"date": "20250620"}
```

It honours your **Video Export** preset and **Discord** upload settings.

## 3. Files here

| File                     | What it does                                              |
|--------------------------|----------------------------------------------------------|
| `nina_start.bat`         | `POST /capture/start` (curl)                              |
| `nina_stop.bat`          | `POST /capture/stop` (curl)                               |
| `nina_create_video.bat`  | `POST /video/create` for the newest session (curl)       |
| `nina_capture.ps1`       | PowerShell variant: `start` / `stop` / `video` / `status`|

`curl.exe` ships with Windows 10/11, so the `.bat` files need no extra install.
If you changed the port, edit it in each script.

## 4. Using them in NINA

In a sequence, add an **External Script** instruction and point it at the script:

- **At sequence start:** `nina_start.bat`
- **At sequence end:** `nina_stop.bat`
- **After stop (optional):** `nina_create_video.bat`

The `.bat` files use `curl -f`, so a failed request returns a non-zero exit code
that NINA can detect.

## 5. Quick manual test

```bat
curl http://127.0.0.1:8787/status
curl -X POST http://127.0.0.1:8787/capture/start
curl -X POST http://127.0.0.1:8787/capture/stop
```
