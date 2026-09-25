# Threat model and non-goals

## Boundary

A private-context parent can delegate to a non-ZDR expert, creating an external disclosure boundary. This plugin is a deterministic veto at the `delegate_task` handoff.

## Assets protected at this boundary

- direct identifiers and configured private terms;
- credentials and token-bearing links;
- local/private paths and attachments;
- raw content supplied in `goal` or `context`.

## Guarantees for tested cases

- blocked calls never reach the child-start callback;
- allowed calls preserve original arguments unchanged;
- receipts omit source content and identifiers;
- local detector/dictionary/audit errors produce a block result.

## Non-goals

- Natural-language anonymity proof or semantic PII classification.
- Rewriting, redacting, canonicalizing, summarizing, or creating a child-safe prompt.
- Provider ZDR controls, fallback/auxiliary routing, memory isolation, gateway authorization, or child capability grants.
- Enabling the plugin or changing any live profile.

## Residual risk

A generic-looking brief can still identify someone through rare fact combinations. The parent must create a minimal generic brief only when safe; otherwise answer locally or ask for a minimal general clarification. Do not treat an allow decision as a privacy guarantee.
