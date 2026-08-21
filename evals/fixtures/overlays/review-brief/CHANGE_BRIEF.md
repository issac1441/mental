# Change brief — carrier send timeout (approved)

status: approved

## Approved delta

Add a 2-second timeout to the carrier `send` call inside dispatch: a send
that does not answer within 2 seconds is treated as a `CarrierTimeout` and
follows the existing retry path.

## Explicitly out of scope (not approved)

- Any change to retry counts, backoff timing, or jitter.
- Any change to which error types are retryable.
- Any change to receipts, dead-letter behavior, pricing, or inventory.

Human decision: approved 2026-08-19 (timeout only, semantics otherwise
unchanged).
