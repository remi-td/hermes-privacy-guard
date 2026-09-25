# Operations and acceptance procedure

## Preconditions

1. Obtain explicit approval before installing or enabling the plugin in a target profile.
2. Keep that profile's existing live configuration unchanged until synthetic tests pass.
3. Use only synthetic markers. Never place private user data, identifiers, credentials, or real dictionary terms in terminals, reports, Vault notes, or commits.
4. Independently restrict child capabilities. This guard only vetoes handoff inputs.

## Install without enabling

```bash
hermes -p <profile> plugins install <owner>/hermes-privacy-guard --no-enable
hermes -p <profile> plugins doctor hermes-privacy-guard --ci
```

Confirm it declares only the `pre_tool_call` hook. It has no Python dependencies, network calls, tools, shell commands, or telemetry.

## Optional private terms

Create `$HERMES_HOME/privacy/delegation-private-terms.json` with `0600` permissions. Values are ignored. Never use real terms in acceptance tests.

## Enforce-mode acceptance tests

After explicit enablement, start a fresh target-profile session and run only synthetic cases:

| Case | Expected result |
|---|---|
| synthetic email | blocked before child creation |
| synthetic phone | blocked before child creation |
| synthetic credential token | blocked before child creation |
| synthetic private path/token URL | blocked before child creation |
| synthetic configured term | blocked before child creation |
| image input | blocked before child creation |
| batch input | blocked before child creation |
| delegated control action | blocked before child creation |
| malformed call or broken dictionary | blocked before child creation |
| generic clean `goal` / `context` | allowed unchanged |

For each block, inspect only category names and audit shape. Do not copy raw prompt text into records. Confirm the child cache/transcript received no attempted call for sensitive cases. For a clean call, compare the child-bound object to the original synthetic object and confirm it is byte-for-byte unchanged.

## Audit inspection

Audit rows may include only:

```json
{"categories":{"email":1},"decision":"blocked","schema":"hermes-privacy-guard/v1-block-only","tool":"delegate_task","ts":"..."}
```

Verify no free text, match, hash, session/sender/packet identifier, path, URL, or private term is present. Check parent mode `0700` and log mode `0600`.

## Rollback

Disable/remove through Hermes plugin management and restart/rotate only as approved. Never work around a false positive by changing the guard to redact or forward modified content. Keep the target profile on its existing approved route until policy is reviewed.
