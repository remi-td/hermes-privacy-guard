# Hermes integration contract

The production integration is a native, profile-local Hermes plugin. It registers exactly one `pre_tool_call` callback.

Hermes invokes the callback on the agent-tool execution path before its child-start execution callback. A block directive becomes the tool result and prevents `delegate_task` from constructing or starting a child. Hermes' plugin dispatcher treats a `pre_tool_call` timeout as fail-closed; this plugin itself blocks on every local error.

```python
def register(ctx):
    ctx.register_hook("pre_tool_call", pre_tool_call)
```

The callback ignores every tool except `delegate_task`. For a clean allowed call it returns `None`; it does not emit a `modify` directive and does not copy or mutate `args`.

## Profile-scoped storage

The callback resolves Hermes' active home with `hermes_constants.get_hermes_home()` at call time. That keeps audit and optional dictionary paths profile-scoped in a multiplexed gateway rather than capturing a launch-profile path at import time.

- Audit: `$HERMES_HOME/privacy-audit/delegation.jsonl`
- Optional dictionary: `$HERMES_HOME/privacy/delegation-private-terms.json`

The plugin uses no environment variables for behavioral configuration and no network I/O.

## Compatibility

Target: current native `plugin.yaml` / `register(ctx)` interface and documented `pre_tool_call` contract. No core Hermes files are modified. The package has no runtime Python dependencies.

## Explicit enablement

Directory placement/install is not activation. Hermes user plugins are opt-in through `plugins.enabled`; activate only with explicit operator approval. This repository intentionally contains no script or configuration that edits any profile.
