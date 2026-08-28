"""
Shared application logging.

One logger tree, rooted at "rtsp": the GUI attaches (and detaches) the rotating
file handler on the root when the Integrations tab's "Write a log file" box is
toggled, and every module logs through a child from get_logger(area) -
"rtsp.capture", "rtsp.export", ... Records propagate to the root's handler, so
toggling the checkbox captures the whole tree with no per-module wiring.

With file logging off the root sits at WARNING with only a NullHandler, so the
DEBUG calls sprinkled through the app are dropped at the isEnabledFor() check -
near-zero cost on hot paths. Modules should use %-style lazy formatting
(LOG.debug("x %s", y), not f-strings) so disabled logging also skips the
string work.

Stdlib-only and import-light on purpose: every module imports this, including
the ones tests load without a GUI.
"""

import logging

ROOT_NAME = "rtsp"


def get_logger(area: str = None) -> logging.Logger:
    """The root logger (no area) or a child like "rtsp.capture".

    Loggers are keyed globally by name, so it doesn't matter whether a module
    was imported as `src.foo` or `foo` - same name, same logger.
    """
    return logging.getLogger(f"{ROOT_NAME}.{area}" if area else ROOT_NAME)


def mask_secrets(value):
    """Deep-copy dicts/lists with password-ish values replaced by "****".

    For logging config snapshots: the camera and MQTT passwords live in plain
    dicts, and a log file must never carry them. Non-container values pass
    through unchanged.
    """
    if isinstance(value, dict):
        return {
            key: ("****" if ("password" in str(key).lower() and val) else mask_secrets(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    return value


def trunc(value, limit: int = 300) -> str:
    """repr() capped at `limit` chars, for logging arbitrary payloads safely."""
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + f"...(+{len(text) - limit} chars)"
