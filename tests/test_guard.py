import importlib.util
import json
import os
import stat
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_guard(monkeypatch, home: Path):
    fake_constants = types.ModuleType("hermes_constants")
    fake_constants.get_hermes_home = lambda: home
    monkeypatch.setitem(sys.modules, "hermes_constants", fake_constants)
    spec = importlib.util.spec_from_file_location("privacy_guard_under_test", ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("args", "category"),
    [
        ({"goal": "contact synthetic@example.test", "context": ""}, "email"),
        ({"goal": "call +1 202 555 0199", "context": ""}, "phone"),
        ({"goal": "use sk_abcdefghijklmnop", "context": ""}, "credential"),
        ({"goal": "read /srv/private/report", "context": ""}, "private_path_or_url"),
        ({"goal": "review", "context": "", "images": ["anything"]}, "attachment"),
        ({"tasks": [{"goal": "generic"}]}, "batch_delegation"),
        ({"goal": "generic", "action": "stop"}, "delegated_control_action"),
        ({"goal": 7}, "malformed_request"),
    ],
)
def test_sensitive_delegation_is_blocked_and_audited(monkeypatch, tmp_path, args, category):
    guard = load_guard(monkeypatch, tmp_path)

    result = guard.pre_tool_call("delegate_task", args)

    assert result and result["action"] == "block"
    assert category in result["message"]
    row = json.loads((tmp_path / "privacy-audit" / "delegation.jsonl").read_text())
    assert row["decision"] == "blocked"
    assert row["categories"] == {category: 1}
    assert set(row) == {"ts", "schema", "tool", "decision", "categories"}


def test_clean_delegation_is_allowed_without_mutation(monkeypatch, tmp_path):
    guard = load_guard(monkeypatch, tmp_path)
    args = {"goal": "Compare general gardening tools", "context": "Use public sources only."}
    original = dict(args)

    result = guard.pre_tool_call("delegate_task", args)

    assert result is None
    assert args == original
    row = json.loads((tmp_path / "privacy-audit" / "delegation.jsonl").read_text())
    assert row["decision"] == "allowed"
    assert row["categories"] == {}


def test_private_term_dictionary_is_local_and_its_value_is_ignored(monkeypatch, tmp_path):
    private_dir = tmp_path / "privacy"
    private_dir.mkdir(mode=0o700)
    dictionary = private_dir / "delegation-private-terms.json"
    dictionary.write_text(json.dumps({"synthetic-marker": "must-not-be-used"}))
    dictionary.chmod(0o600)
    guard = load_guard(monkeypatch, tmp_path)

    result = guard.pre_tool_call("delegate_task", {"goal": "synthetic-marker", "context": ""})

    assert result and "configured_term" in result["message"]
    assert "synthetic-marker" not in result["message"]
    assert "must-not-be-used" not in result["message"]


def test_bad_dictionary_fails_closed(monkeypatch, tmp_path):
    private_dir = tmp_path / "privacy"
    private_dir.mkdir(mode=0o700)
    dictionary = private_dir / "delegation-private-terms.json"
    dictionary.write_text("not json")
    dictionary.chmod(0o600)
    guard = load_guard(monkeypatch, tmp_path)

    result = guard.pre_tool_call("delegate_task", {"goal": "generic", "context": ""})

    assert result == {"action": "block", "message": "Privacy broker: local detection unavailable; delegation blocked."}
    row = json.loads((tmp_path / "privacy-audit" / "delegation.jsonl").read_text())
    assert row["decision"] == "error"
    assert row["categories"] == {"detector_unavailable": 1}


def test_audit_permissions_and_content_are_metadata_only(monkeypatch, tmp_path):
    guard = load_guard(monkeypatch, tmp_path)
    private = "secret synthetic@example.test /srv/family"

    guard.pre_tool_call("delegate_task", {"goal": private, "context": ""})

    audit_dir = tmp_path / "privacy-audit"
    audit = audit_dir / "delegation.jsonl"
    assert stat.S_IMODE(audit_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(audit.stat().st_mode) == 0o600
    content = audit.read_text()
    assert private not in content
    assert "synthetic@example.test" not in content
    assert "/srv/family" not in content


def test_unrelated_tool_is_ignored_and_not_audited(monkeypatch, tmp_path):
    guard = load_guard(monkeypatch, tmp_path)

    assert guard.pre_tool_call("read_file", {"path": "/srv/private"}) is None
    assert not (tmp_path / "privacy-audit").exists()
