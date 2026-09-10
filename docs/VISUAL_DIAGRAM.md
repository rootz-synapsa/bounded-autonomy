# Visual Architecture Diagram

## Mermaid Version

Copy ؠ�������事取一点到松 —:
- https://mermaid.live (preview + export PNG/SVG)
- draw.io (import mermaid)
- GitHub README (render ขไุฐม่)

### Flow

ACTION CANDIDATE -> DECISION ENGINE -> AUTO / SUPERVISED / BLOCK

AUTO path:
  Decision Engine -> AUTO -> Execute immediately

SUPERVISED path:
  Decision Engine -> SUPERVISED -> Authorization Lifecycle
  -> PENDING -> GRANTED (or EXPIRED/INVALIDATED)
  -> Revalidation Gate -> PASS: Execute / FAIL: Cancel

## Decision Taxonomy

| Decision | Condition | Action |
|----------|----------|--------|
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


## Side Annotations

Policy Ceiling = 10
Autonomous Envelope <= 6
Supervised Envelope 7 - 10


## Tagline

Optimize aggressively. Execute only within authority.


## Usage

- Slide 1: Full diagram + tagline (title slide)
- Slide 3: Diagram + side annotations (mechanism)
- README: Embed Mermaid (GitHub renders)
- Video: Export PNG 16:9 from Mermaid live
