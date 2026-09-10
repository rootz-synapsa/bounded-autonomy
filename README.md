# Bounded Autonomy

**Bounded governance can reduce total operational friction compared with ungoverned autonomy. Supported in a controlled experiment.**

## Axiom-1: SUPPORTED — CONTROLLED EXPERIMENT ONLY

SAFETY VALUE:       PASS
OPERATIONAL VALUE:  PASS
AXIOM-1 SUPPORT:    SUPPORTED
(in controlled inference-scaling experiment)

Evidence: 30 paired A/B trials / 60 arm executions (3 scenarios x 10 seeds x 2 arms)
- Authority violations: 25 -> 0
- Stale BEFORE execution: 0 -> 0 (governance-failure metric)
- Stale AFTER execution: 20 -> 10 (workload-evolution metric, see taxonomy)
- Cost overhead: -19% (cheaper)
- SLA degradation: +10.9% (acceptable trade-off)

Scope: simulator, 3 workload scenarios, specific policy configuration.
This is an existence proof under tested conditions, not a universal law.

See docs/RESULTS.md and docs/MEASUREMENT_CORRECTION.md.

## What "operational friction" means here

Axiom-1 support is composite evidence, not a single metric:
1. Authority correctness: 25 -> 0 violations
2. Stale-before-execution prevention: 0 in governed arm
3. Cost: -19% vs ungoverned baseline
4. SLA trade-off: +10.9%, within predefined acceptance bound

We do NOT claim governed execution is faster in latency terms.
SLA degradation is positive; the gain is in cost and authority correctness.

## Stale action taxonomy (why 20 -> 10 is not a contradiction)

- Stale BEFORE execution: justification already false at execution time.
  This is a governance failure. Governed arm: 0.
- Stale AFTER execution: action was justified at execution time, but the
  workload recovered 1-2 steps later. This is overprovisioning, not a safety
  failure. M8 revalidation cannot prevent it because it was valid at decision
  time. Governed arm halves it (20 -> 10) via earlier bounded scaling.

M8 killer property: authorization is not permanent permission.
PENDING -> GRANTED -> context changes -> INVALIDATED -> CANCELLED.
"The action was approved. It was no longer justified. So it never executed."

## Architecture (H0 -> M8)

- H0: ungoverned baseline (control)
- M5: fail-closed enforcement (AUTO/BLOCK)
- M6: bounded authority envelope (AUTO/SUPERVISED/BLOCK)
- M7: authorization lifecycle (PENDING/GRANTED/EXPIRED/INVALIDATED/CONSUMED)
- M8: revalidation gate (authority valid only while context remains valid)

## Reproduce

python experiments/run_m9.py                  # 30 paired trials
python experiments/demo_run.py --scene all    # 3-scene demo
python -m unittest discover -s tests -v       # 28 tests

## Docs

- docs/EXPERIMENT.md - methodology + predefined acceptance criteria
- docs/RESULTS.md - verdicts and analysis
- docs/MEASUREMENT_CORRECTION.md - metric taxonomy correction history
- docs/DEMO_SCRIPT.md / docs/SPEAKER_NOTES.md - 90-second pitch
- docs/VISUAL_DIAGRAM.md - architecture flow (Mermaid)

## Status

Demo Freeze v1 active.
Next: M10 adversarial replication / boundary test —
find the measurable conditions where Axiom-1 stops holding.
