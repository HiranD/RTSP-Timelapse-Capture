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


# A key containing any of these (case-insensitive) is a secret and its value is
# masked. Substring match on purpose - "mqtt_password", "discord_webhook_url",
# "api_key"... - and biased towards over-masking: hiding a harmless value costs
# a little diagnostic detail, leaking a real one costs a credential. Any new
# config field that carries a credential MUST have one of these words in its
# name; the full-config test in tests/test_file_logging.py pins the known ones.
_SECRET_KEY_WORDS = ("password", "webhook", "token", "secret", "key")


def _is_secret_key(key) -> bool:
    lowered = str(key).lower()
    return any(word in lowered for word in _SECRET_KEY_WORDS)


def mask_secrets(value):
    """Deep-copy dicts/lists with secret values replaced by "****".

    For logging config snapshots: the camera and MQTT passwords and the Discord
    webhook URL live in plain dicts, and a log file must never carry them -
    it's the file remote users are asked to send in for diagnosis. Non-container
    values pass through unchanged; empty secrets stay empty so the log still
    shows whether one is configured.

    Until 2026-09-06 only "password" keys were masked, so the webhook URL (which
    lets anyone post to that channel) went into app.log verbatim on every
    capture start.
    """
    if isinstance(value, dict):
        return {
            key: ("****" if (_is_secret_key(key) and val) else mask_secrets(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(item) for item in value]
    return value


def trunc(value, limit: int = 300) -> str:
    """repr() capped at `limit` chars, for logging arbitrary payloads safely."""
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + f"...(+{len(text) - limit} chars)"
