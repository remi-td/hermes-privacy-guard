# Hermes Privacy Guard

A production-oriented Hermes plugin that provides a **fail-closed, block-only** `pre_tool_call` boundary for non-ZDR `delegate_task` handoffs.

## Security contract

The guard inspects a proposed delegation locally, appends one metadata-only audit receipt, then either:

- returns `None`, allowing the **original, unchanged** delegation call; or
- returns a generic block directive **before** Hermes dispatches `delegate_task`, so no child starts.

It never redacts, rewrites, summarizes, generalizes, stores a private packet, hashes source content, or forwards a replacement prompt. A blocked parent must prepare a new de-identified brief in its ZDR context or answer locally.

### Block conditions

- configured private term from a profile-local owner-only dictionary;
- email address, phone-like number, credential-like token, local/private path, or token-bearing URL;
- images/attachments, batch delegation, delegated control actions, malformed arguments;
- unreadable or malformed private-term dictionary; or
- unexpected guard/audit failure.

Detection is a deterministic baseline, not proof that arbitrary free text is anonymous. Do not delegate when unsure.

## Audit privacy

Each attempted `delegate_task` gets one JSONL receipt at:

```text
$HERMES_HOME/privacy-audit/delegation.jsonl
```

The directory and log are forced to owner-only mode (`0700` / `0600`). They are intentionally outside the Vault and normal chat logs. A row contains only UTC timestamp, schema, tool, decision, and category counts. It never records text, matches, hashes, sender/session/packet IDs, names, locations, paths, URLs, or raw arguments.

## Optional private-term dictionary

To detect owner-defined terms, create this file in the target profile home, not the Vault:

```text
$HERMES_HOME/privacy/delegation-private-terms.json
```

It must be a `0600` JSON string-to-string object. Only keys are detection terms; values are ignored and are never used as replacement mappings. Do not put this file in Git, the Vault, logs, or test fixtures.

```json
{
  "synthetic-private-marker": "ignored"
}
```

No dictionary means that configured-term detection is simply absent; all built-in block conditions remain active.

## Installation — deliberately not automatic

This repository does **not** install, enable, or change a live Hermes profile. Review it first, then use an explicit operator-approved installation:

```bash
hermes -p <profile> plugins install <owner>/hermes-privacy-guard --no-enable
hermes -p <profile> plugins doctor hermes-privacy-guard --ci
hermes -p <profile> plugins enable hermes-privacy-guard
```

Enablement changes the running profile and requires explicit approval. Restart/rotate the relevant Hermes session only after completing the synthetic acceptance checks in `docs/OPERATIONS.md`. Keep the delegated child least-privilege independently (for example, one child, depth one, no MCP inheritance, and only `web` or no child tools).

## Development and verification

```bash
python -m pytest -q
# Full Hermes dispatch integration test:
HERMES_SOURCE=/path/to/hermes-agent python -m pytest -q tests/test_hermes_integration.py
# Native plugin registration check against the installed/current Hermes:
hermes plugins doctor . --ci
```

The integration test asserts that a sensitive `delegate_task` is blocked by the real Hermes agent-tool pre-hook path and that the child-start callback is never reached.

## Scope

The guard can be deployed only to a profile whose policy authorizes a non-ZDR delegation lane. It does not itself make any provider route safe, private, or approved.

See `docs/OPERATIONS.md`, `docs/THREAT_MODEL.md`, and `docs/INTEGRATION.md`.
