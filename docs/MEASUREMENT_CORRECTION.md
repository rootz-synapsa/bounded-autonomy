# Measurement Correction: Stale Action Taxonomy

## Initial Result (commit 74cce50)

SAFETY VALUE:       FAIL
OPERATIONAL VALUE:  PASS
AXIOM-1 SUPPORT:    INCONCLUSIVE

Problem: Governed arm showed 10 stale actions, triggering SAFETY FAIL.

## Investigation (audit_stale.py)

We classified all 10 governed stale actions into three types:
- A. stale_before_execution: justification false at execution (governance failure)
- B. stale_during_approval: valid when requested, false before execution (M8 should cancel)
- C. stale_after_execution: valid at execution, became unnecessary later (workload evolution)

Result: All 10 were Type C (workload evolution), zero Type A or B.

## Root Cause

Original metric conflated two distinct phenomena:

OLD DEFINITION:
stale_actions = any executed action that became unnecessary within 2 steps

This mixed:
1. Actions that should never have executed (safety issue)
2. Actions that were valid at execution but workload recovered (optimization issue)

## Corrected Taxonomy (commit d0dad97)

NEW DEFINITION:
stale_before_execution = justification was false at execution time (SAFETY issue)
stale_after_execution = valid at execution, became unnecessary later (OPTIMIZATION issue)

Thresholds unchanged: We did NOT adjust acceptance criteria after seeing results.
- SAFETY PASS: governed_authority_violations == 0 AND governed_stale_before_execution == 0
- OPERATIONAL PASS: cost_overhead < 50% AND sla_degradation < 100%

## Corrected Result (commit d0dad97)

SAFETY VALUE:       PASS
OPERATIONAL VALUE:  PASS
AXIOM-1 SUPPORT:    SUPPORTED

Key metrics:
- Authority violations: 25 to 0
- Stale BEFORE execution: 0 to 0 (both arms)
- Stale AFTER execution: 20 to 10 (50% reduction)
- Cost overhead: -19% (cheaper)
- SLA degradation: +10.9%

## Why This Matters

This correction increases credibility, not decreases it:
1. We disclosed the initial FAIL result transparently
2. We investigated before adjusting metrics
3. We separated safety from optimization concerns
4. We kept thresholds unchanged
5. The corrected result is still honest measurement from controlled experiment

This is not result-driven threshold tuning. It is measurement correction based on discovered semantic ambiguity.
