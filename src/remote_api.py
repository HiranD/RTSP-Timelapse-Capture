"""
Remote Control HTTP API - localhost-only REST endpoints for external control.

Lets external scripts (e.g. NINA's "External Script" instruction) start/stop
capture and trigger nightly video creation over HTTP. Opt-in, off by default,
and bound to 127.0.0.1 only. Standard-library only (http.server) - no new deps.

Security model: the server binds to the loopback interface, AND every request's
Host header is checked against a loopback allowlist (localhost / 127.0.0.1) to
block the browser DNS-rebinding / CSRF case. There is no auth token (see issue
#12): the API is intended for local-machine use only.

This module is intentionally Tk-agnostic. The GUI passes in plain callables that
already marshal work onto the Tk main thread, so the handler here never touches
Tkinter.

Endpoints (all JSON):
    GET  /health         -> {"ok": true, "version": "..."}
    GET  /status         -> {"capturing", "state", "frame_count", ...}
    POST /capture/start  -> 202 {"status": "starting", ...}  | 400 {"error"}
    POST /capture/stop   -> 200 {"status": "stopping", ...}  | 400 {"error"}
    POST /video/create   -> 202 {"status", "date", "since"}  | 400/404 {"error"}
        optional JSON body: {"date": "YYYYMMDD", "since": "YYYYMMDD-HHMMSS"}
        (no date -> newest session; since -> only frames captured at/after it)
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Hostnames accepted in the Host header (loopback only).
_ALLOWED_HOSTS = {"localhost", "127.0.0.1"}


class RemoteControlServer:
    """A small localhost HTTP server exposing capture/video controls.

    All app interaction goes through the callables passed to __init__; the
    server never imports or touches the GUI directly.
    """

    def __init__(self, *, on_start, on_stop, on_create_video, get_status,
                 version="", host="127.0.0.1", port=8787, log=None):
        """
        Args:
            on_start():  () -> (ok: bool, error: str | None)
            on_stop():   () -> (ok: bool, error: str | None)
            on_create_video(date, since): (date, since: str | None)
                         -> (ok: bool, message: str, http_code: int, resolved_date: str | None)
            get_status(): () -> dict (serialised verbatim for GET /status)
            version: app version string reported by GET /health.
            host: bind address (loopback).
            port: TCP port. Use 0 to bind an ephemeral port (tests read .port).
            log: optional callable(level: str, message: str) for logging.
        """
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_create_video = on_create_video
        self._get_status = get_status
        self._version = version
        self.host = host
        self.port = port
        self._log = log or (lambda level, msg: None)
        self._server = None
        self._thread = None

    # -------------------------------------------------------------- lifecycle

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self):
        """Start serving on a daemon thread.

        Raises OSError (e.g. WinError 10048 "address already in use") if the
        port is busy - callers surface this to the user.
        """
        if self.is_running:
            return
        handler = self._make_handler()
        # ThreadingHTTPServer so one slow request can't block the others.
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._server.daemon_threads = True
        # Reflect the actually-bound port (relevant when port=0 was requested).
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="RemoteControlServer",
            daemon=True,
        )
        self._thread.start()
        self._log("INFO", f"Remote control API listening on {self.base_url}")

    def stop(self):
        """Stop serving and release the port."""
        if not self.is_running:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
        finally:
            self._server = None
            self._thread = None
            self._log("INFO", "Remote control API stopped")

    # ---------------------------------------------------------------- handler

    def _make_handler(self):
        server = self  # closure for the request handler

        class Handler(BaseHTTPRequestHandler):
            # Keep the default access logging out of stderr; route to our log.
            def log_message(self, fmt, *args):
                server._log("DEBUG", "%s - %s" % (self.address_string(), fmt % args))

            # -- helpers ----------------------------------------------------

            def _send_json(self, code, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # client hung up; nothing to do

            def _host_ok(self) -> bool:
                # Host header may include a port; strip it. Reject anything that
                # isn't loopback (blocks DNS-rebinding from a browser).
                host = self.headers.get("Host", "")
                hostname = host.rsplit(":", 1)[0] if ":" in host else host
                return hostname in _ALLOWED_HOSTS

            def _read_body(self):
                """Parse the optional JSON request body; {} if absent/invalid."""
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return {}
                return data if isinstance(data, dict) else {}

            @staticmethod
            def _opt_str(data, key):
                """Return a stripped, non-empty string field, else None."""
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                return None

            # -- dispatch ---------------------------------------------------

            def do_GET(self):
                self._dispatch("GET")

            def do_POST(self):
                self._dispatch("POST")

            def do_PUT(self):
                self._dispatch("PUT")

            def do_DELETE(self):
                self._dispatch("DELETE")

            def _dispatch(self, method):
                # Reject non-local hosts before doing anything else.
                if not self._host_ok():
                    self._send_json(403, {"error": "forbidden: non-local Host header"})
                    return
                try:
                    self._route(method)
                except Exception as e:  # never leak a traceback to the client
                    server._log("ERROR", f"Remote API handler error: {e}")
                    self._send_json(500, {"error": "internal error"})

            def _route(self, method):
                path = self.path.split("?", 1)[0]
                routes = {
                    ("GET", "/health"): self._health,
                    ("GET", "/status"): self._status,
                    ("POST", "/capture/start"): self._start,
                    ("POST", "/capture/stop"): self._stop,
                    ("POST", "/video/create"): self._video,
                }
                handler = routes.get((method, path))
                if handler:
                    handler()
                    return
                # Known path but wrong method -> 405; otherwise 404.
                if path in {p for (_, p) in routes}:
                    self._send_json(405, {"error": "method not allowed"})
                else:
                    self._send_json(404, {"error": "not found"})

            # -- endpoints --------------------------------------------------

            def _health(self):
                self._send_json(200, {"ok": True, "version": server._version})

            def _status(self):
                self._send_json(200, server._get_status())

            def _start(self):
                ok, err = server._on_start()
                if ok:
                    self._send_json(202, {"status": "starting", **server._get_status()})
                else:
                    self._send_json(400, {"error": err or "failed to start capture"})

            def _stop(self):
                ok, err = server._on_stop()
                if ok:
                    self._send_json(200, {"status": "stopping", **server._get_status()})
                else:
                    self._send_json(400, {"error": err or "failed to stop capture"})

            def _video(self):
                body = self._read_body()
                date = self._opt_str(body, "date")
                since = self._opt_str(body, "since")
                ok, message, code, resolved = server._on_create_video(date, since)
                key = "status" if ok else "error"
                # Echo the resolved target (e.g. the newest session) when known,
                # else fall back to whatever the caller sent.
                self._send_json(code, {key: message, "date": resolved or date, "since": since})

        return Handler
