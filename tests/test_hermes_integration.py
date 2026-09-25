"""Real Hermes dispatch proof: privacy block happens before delegate_task dispatch."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES_SOURCE = os.environ.get("HERMES_SOURCE")

pytestmark = pytest.mark.skipif(not HERMES_SOURCE, reason="set HERMES_SOURCE to a Hermes Agent checkout")


def test_sensitive_delegation_is_blocked_before_delegate_handler_starts(monkeypatch, tmp_path):
    source = Path(HERMES_SOURCE)
    assert (source / "model_tools.py").is_file()
    sys.path.insert(0, str(source))
    try:
        import yaml
        from types import SimpleNamespace
        from hermes_cli import plugins as plugins_mod
        from agent import tool_executor

        home = tmp_path / "profile"
        plugin_dir = home / "plugins" / "hermes-privacy-guard"
        plugin_dir.parent.mkdir(parents=True)
        shutil.copytree(ROOT, plugin_dir, ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"))
        (home / "config.yaml").write_text(yaml.safe_dump({"plugins": {"enabled": ["hermes-privacy-guard"]}}))
        monkeypatch.setenv("HERMES_HOME", str(home))

        manager = plugins_mod.PluginManager()
        manager.discover_and_load()
        loaded = manager._plugins["hermes-privacy-guard"]
        assert loaded.enabled, loaded.error
        monkeypatch.setattr(plugins_mod, "_plugin_manager", manager)

        child_starts = []
        post_results = []
        ref = SimpleNamespace(
            name="delegate_task",
            args={"goal": "Contact synthetic@example.test", "context": "Synthetic integration marker only."},
            task_id="synthetic-task",
            call_id="synthetic-call",
            trace=[],
            emit_post=lambda _agent, result, **_outcome: post_results.append(result),
        )
        state = SimpleNamespace(args=ref.args, blocked=False)
        result = tool_executor._dispatch_authorized_once(
            SimpleNamespace(),
            state,
            ref,
            execute=lambda _args: child_starts.append("started"),
            scope_block=None,
            display_index=None,
            begin_execution=None,
            authorization_gate=None,
        )

        assert child_starts == [], "execute is the child-start path and must not run"
        assert state.blocked is True
        parsed = json.loads(result)
        assert "error" in parsed
        assert "email" in parsed["error"].lower()
        assert post_results == [result]
        receipt = json.loads((home / "privacy-audit" / "delegation.jsonl").read_text())
        assert receipt["decision"] == "blocked"
        assert receipt["categories"] == {"email": 1}
    finally:
        sys.path.remove(str(source))
