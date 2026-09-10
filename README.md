# Bounded Autonomy

Governed AI is faster than ungoverned AI. Supported in controlled experiment.

## Axiom-1: Supported

SAFETY VALUE:       PASS
OPERATIONAL VALUE:  PASS
AXIOM-1 SUPPORT:    SUPPORTED (in controlled inference-scaling experiment)

Evidence: 30 paired A/B trials / 60 arm executions (3 scenarios x 10 seeds x 2 arms)
- Authority violations: 25 to 0
- Stale BEFORE execution: 0 to 0
- Stale AFTER execution: 20 to 10 (50% reduction)
- Cost overhead: -19% (cheaper)
- SLA degradation: +10.9% (acceptable)

Scope: Supported in our controlled inference-scaling experiment (simulator, 3 scenarios, specific policy configuration).

See docs/RESULTS.md for full analysis.
See docs/MEASUREMENT_CORRECTION.md for honest disclosure of metric taxonomy correction.

## Narrative

Autonomous infrastructure can optimize aggressively without receiving unlimited authority.

In 30 paired controlled trials, bounded governance eliminated observed authority violations while reducing simulated infrastructure cost by 19%, with a 10.9% SLA trade-off. Context-bound revalidation also prevented approved actions from executing after their justification became stale.

## Architecture

H0 to M8 evolution:
- H0: Ungoverned baseline (control group)
- M5: Basic enforcement (BLOCK/ALLOW, fail-closed)
- M6: Bounded authority envelope (AUTO/SUPERVISED/BLOCK)
- M7: Authorization lifecycle (PENDING to GRANTED to CONSUMED/EXPIRED/INVALIDATED)
- M8: Revalidation execution gate (authority valid only while reality remains valid)

## Experiment

Methodology: Controlled experiment comparing H0 (ungoverned) vs H1 (governed)
- Same workload, optimizer, seeds, initial state, cost model
- Only difference: governance path
- 30 paired trials / 60 arm executions

Scenarios: Spike, Overshoot, Stale Approval

See docs/EXPERIMENT.md for methodology.

## Killer Scenarios

### M5: 4 to 8 SUPERVISED (not BLOCK)
H0 executes immediately (violates authority). H1 routes through SUPERVISED (within supervised envelope, awaits approval).

Demonstrates: Governance does not forbid autonomy. It defines bounds.

### M8: Stale Approval Prevention
T0  p95=487ms   candidate: scale 6 to 7   decision=SUPERVISED
T1  human approves                     authorization=GRANTED
T2  workload changes                   p95=165ms
T3  revalidation fails                 INVALIDATED, CANCELLED

Hero evidence: The action was approved. It was no longer justified. So it never executed.

## Running the Experiment

python experiments/run_m9.py

Output: results/m9/verdicts.json

## Test Suite

28 tests covering H0 baseline, H1 taxonomy, M5-M8 enforcement, M9 experiment mechanics.

python -m unittest discover -s tests -v

## License

MIT
