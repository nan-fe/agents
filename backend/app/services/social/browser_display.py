"""Detect whether Playwright can open a user-interactive headed browser."""

from __future__ import annotations

import os
import sys


def _env_flag(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def has_interactive_display() -> bool:
    """True when login/OAuth may use a visible browser the operator can interact with."""
    forced_browserless = _env_flag("SOCIAL_OAUTH_BROWSERLESS")
    if forced_browserless is True:
        return False
    if forced_browserless is False:
        return True

    forced_interactive = _env_flag("SOCIAL_OAUTH_INTERACTIVE")
    if forced_interactive is True:
        return True
    if forced_interactive is False:
        return False

    if sys.platform in ("darwin", "win32"):
        return True

    display = os.environ.get("DISPLAY", "").strip()
    if not display:
        return False
    # xvfb in Docker commonly uses :99; treat it as non-interactive.
    if display.startswith(":99"):
        return False
    return True


def use_browserless_oauth() -> bool:
    """OAuth should complete in the user's browser (remote server / Docker)."""
    return not has_interactive_display()


def resolve_login_headless(*, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    return not has_interactive_display()
