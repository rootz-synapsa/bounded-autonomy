# Bounded Autonomy: Architecture Diagram

## Core Flow

Agent Intent -> Decision Engine -> AUTO / SUPERVISED / BLOCK

AUTO path:
  Decision Engine -> AUTO -> Execute immediately

SUPERVISED path:
  Decision Engine -> SUPERVISED -> Authorization Lifecycle
  -> PENDING -> GRANTED (or EXPIRED/INVALIDATED)
  -> Revalidation Gate -> PASS: Execute / FAIL: Cancel

## Decision Taxonomy

| Decision | Condition | Action |
|----------|-----------|--------|
| AUTO | Within auto_scale_max (6) | Execute immediately |
| SUPERVISED | Between 6 and supervised_scale_max (10) | Request bounded approval |
| BLOCK | Exceeds absolute_max (10) or invariant violation | Fail-closed |

## Authorization Lifecycle

PENDING -> GRANTED -> CONSUMED
PENDING -> EXPIRED (TTL elapsed)
GRANTED -> EXPIRED (TTL elapsed)
GRANTED -> INVALIDATED (state drift / action mismatch)

## Revalidation Gate (M8)

Before executing GRANTED authorization:
1. Action binding: exact action approved?
2. Objective binding: justification still true?
3. State binding: state matches grant-time snapshot?
4. Invariant check: no forbidden actions?
5. Policy/Authority: still within envelopes?

Any fail -> INVALIDATED -> CANCELLED_AFTER_REVALIDATION

## Key Insight

Authority is valid only while reality remains valid.
