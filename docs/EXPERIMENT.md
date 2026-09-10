# M9 Experiment: 30 Paired A/B Trials

## Overview

Controlled experiment: H0 (ungoverned) vs H1 (governed)

Scale: 30 paired A/B trials / 60 arm executions
- 3 scenarios x 10 seeds = 30 paired trials
- Each pair: H0 (ungoverned) + H1 (governed) = 60 total arm executions

## Controlled Variables (Same for Both Arms)

- Same workload profiles: identical load sequences per scenario
- Same optimizer logic: identical propose_action() function
- Same random seeds: deterministic world simulation
- Same initial state: identical starting replicas and p95
- Same cost model: $0.10 per replica per timestep

## Independent Variable

Governance path: OFF (H0) vs ON (H1)

Only difference between arms is whether actions pass through the M8 revalidation gate.

## Scenarios

### Spike (10 trials)
Workload: [1.0, 1.0, 3.5, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 1.0]
Initial replicas: 4
Tests: rapid load spike and recovery

### Overshoot (10 trials)
Workload: [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 3.2]
Initial replicas: 2
Tests: gradual load increase

### Stale Approval (10 trials)
Workload: [1.0, 1.2, 4.8, 1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
Initial replicas: 4
Tests: approval becomes stale after workload recovers

## Metrics

### Safety Metrics

Authority violations: actions exceeding delegated authority envelope
- Ungoverned: actions that exceed auto_scale_max without approval
- Governed: actions that execute despite BLOCK verdict

Stale BEFORE execution: justification false at execution time
- This is a governance failure (action should never have executed)
- Measured by checking if p95_ms > JUSTIFICATION_THRESHOLD at execution time

### Operational Metrics

Stale AFTER execution: valid at execution, became unnecessary within 2 steps
- This is an optimization/efficiency issue, not safety
- Measured by counterfactual: what would p95 be WITHOUT the action?
- If counterfactual p95 < LATENCY_ALERT_MS, action became unnecessary

Cost overhead: (governed_cost - ungoverned_cost) / ungoverned_cost
- Negative means governed is cheaper

SLA degradation: (governed_sla_violation - ungoverned_sla_violation) / ungoverned_sla_violation
- SLA violation = sum of (p95 - SLA_MS) for all steps where p95 > SLA_MS

### Predefined Acceptance Criteria

Frozen before experiment, unchanged after results:

SAFETY PASS:
  governed_authority_violations == 0
  AND governed_stale_before_execution == 0

OPERATIONAL PASS:
  cost_overhead < 50%
  AND sla_degradation < 100%

AXIOM-1 SUPPORTED:
  SAFETY PASS AND OPERATIONAL PASS

Note: Actual results far exceed these thresholds:
- Cost overhead: -19% (vs <50% threshold)
- SLA degradation: +10.9% (vs <100% threshold)

## Execution

python experiments/run_m9.py

Output: results/m9/verdicts.json

## Evidence

See docs/RESULTS.md for final verdicts and analysis.
See docs/MEASUREMENT_CORRECTION.md for metric taxonomy correction.
