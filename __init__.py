"""Block-only privacy boundary for non-ZDR delegation lanes.

This plugin never redacts, rewrites, summarizes, or forwards delegated content.
It either returns ``None`` (so Hermes dispatches the original call unchanged) or
returns a block directive before the delegate_task handler can start a child.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "hermes-privacy-guard/v1-block-only"
TOOL_NAME = "delegate_task"
AUDIT_DIRNAME = "privacy-audit"
AUDIT_FILENAME = "delegation.jsonl"
DICTIONARY_RELATIVE_PATH = Path("privacy") / "delegation-private-terms.json"

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{6,}\d)(?!\w)")
_TOKEN = re.compile(
    r"\b(?:sk|pk|rk|ghp)_[A-Za-z0-9_-]{12,}\b|\bBearer\s+[A-Za-z0-9._-]{12,}\b",
    re.IGNORECASE,
)
_PRIVATE_PATH_OR_URL = re.compile(
    r"(?:\bfile://|(?:^|[\s\"'])/(?:srv|home|root|tmp)/|\.hermes(?:/|\b)|[?&](?:token|key|sig|auth)=)",
    re.IGNORECASE,
)

_BLOCK_MESSAGE_PREFIX = "Privacy broker blocked this delegation because it detected: "
_BLOCK_MESSAGE_SUFFIX = (
    ". Do not retry with the same content. Prepare a new self-contained request using "
    "generic roles, broad time/location ranges, and no identifiers, attachments, credentials, "
    "or private URLs."
)


def _profile_home() -> Path:
    """Resolve the active profile home at call time, including multiplexed turns."""
    from hermes_constants import get_hermes_home

    return get_hermes_home()


def _audit_path(home: Path) -> Path:
    return home / AUDIT_DIRNAME / AUDIT_FILENAME


def _dictionary_path(home: Path) -> Path:
    return home / DICTIONARY_RELATIVE_PATH


def _load_dictionary(home: Path) -> tuple[str, ...]:
    """Load optional local detection terms without retaining values outside this call."""
    path = _dictionary_path(home)
    if not path.exists():
        return ()
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError("private-term dictionary permissions must be 0600 or stricter")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("private-term dictionary must be a JSON string-to-string object")
    return tuple(key for key in value if key)


def _detect(text: str, private_terms: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    folded = text.casefold()
    configured = sum(1 for term in private_terms if term.casefold() in folded)
    if configured:
        counts["configured_term"] = configured
    for category, pattern in (
        ("credential", _TOKEN),
        ("private_path_or_url", _PRIVATE_PATH_OR_URL),
        ("email", _EMAIL),
        ("phone", _PHONE),
    ):
        found = len(pattern.findall(text))
        if found:
            counts[category] = found
    return counts


def _directive_for(args: Any, home: Path) -> tuple[dict[str, str] | None, dict[str, int], str]:
    """Evaluate one delegate_task argument mapping without changing it."""
    if not isinstance(args, Mapping):
        return _blocked("malformed_request"), {"malformed_request": 1}, "blocked"
    if args.get("action") not in (None, "", "spawn"):
        return _blocked("delegated_control_action"), {"delegated_control_action": 1}, "blocked"
    if args.get("images"):
        return _blocked("attachment"), {"attachment": 1}, "blocked"
    if args.get("tasks") is not None:
        return _blocked("batch_delegation"), {"batch_delegation": 1}, "blocked"
    goal = args.get("goal")
    context = args.get("context", "")
    if not isinstance(goal, str) or not isinstance(context, str):
        return _blocked("malformed_request"), {"malformed_request": 1}, "blocked"
    try:
        private_terms = _load_dictionary(home)
    except (OSError, ValueError, json.JSONDecodeError):
        return _unavailable(), {"detector_unavailable": 1}, "error"
    counts = _detect(goal, private_terms)
    for category, count in _detect(context, private_terms).items():
        counts[category] = counts.get(category, 0) + count
    if counts:
        return _blocked(*sorted(counts)), counts, "blocked"
    return None, {}, "allowed"


def _blocked(*categories: str) -> dict[str, str]:
    return {"action": "block", "message": _BLOCK_MESSAGE_PREFIX + ", ".join(categories) + _BLOCK_MESSAGE_SUFFIX}


def _unavailable() -> dict[str, str]:
    return {
        "action": "block",
        "message": "Privacy broker: local detection unavailable; delegation blocked.",
    }


def _audit(home: Path, decision: str, categories: Mapping[str, int]) -> None:
    """Append one metadata-only receipt with owner-only directory and file modes."""
    directory = _audit_path(home).parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    event = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema": SCHEMA,
        "tool": TOOL_NAME,
        "decision": decision,
        "categories": dict(categories),
    }
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    fd = os.open(_audit_path(home), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def pre_tool_call(tool_name: str = "", args: Any = None, **_: Any) -> dict[str, str] | None:
    """Veto unsafe delegation before Hermes invokes the child constructor."""
    if tool_name != TOOL_NAME:
        return None
    try:
        home = _profile_home()
        directive, categories, decision = _directive_for(args, home)
        _audit(home, decision, categories)
        return directive
    except Exception:
        # The audit surface is part of the boundary: an unexpected local failure blocks.
        return {
            "action": "block",
            "message": "Privacy broker internal failure; delegation blocked.",
        }


def register(ctx: Any) -> None:
    """Register the sole policy hook; placement plus explicit enablement is opt-in."""
    ctx.register_hook("pre_tool_call", pre_tool_call)
