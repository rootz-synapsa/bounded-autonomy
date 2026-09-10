# 90-Second Demo Script

## Scene 1: AUTO (0-20s)

Narrator: An AI agent detects high latency and proposes scaling 2 to 4 replicas.
This is within its autonomous envelope.

Run: python experiments/demo_run.py --scene auto

Expected output:
  Agent proposes: SCALE_REPLICAS 2 -> 4
  Decision: AUTO (within auto_scale_max=6)
  Execution: EXECUTED_SUCCESS
  State: replicas 2 -> 4

Key point: No human needed. Bounded autonomy means authority within envelope.

## Scene 2: SUPERVISED (20-45s)

Narrator: Agent wants to scale 4 to 8. Exceeds auto envelope (6) but within supervised (10).

Run: python experiments/demo_run.py --scene supervised

Expected output:
  Agent proposes: SCALE_REPLICAS 4 -> 8
  Decision: SUPERVISED
  Authorization: PENDING -> GRANTED by human-ops-1
  Execution: EXECUTED_SUCCESS

Key point: Governance defines bounds, not forbids autonomy.

## Scene 3: STALE APPROVAL (45-70s)

Narrator: Agent proposes scale 6 to 7 due to high latency. Human approves.
But workload recovers on its own.

Run: python experiments/demo_run.py --scene stale

Expected output:
  T0: p95=487ms, propose SCALE_REPLICAS 6 -> 7, SUPERVISED
  T1: human approves, GRANTED
  T2: workload changes, p95=165ms
  T3: Revalidation -> Objective binding FAIL
      GRANTED -> INVALIDATED -> CANCELLED_AFTER_REVALIDATION

Key point: The action was approved. It was no longer justified. So it never executed.

## Closing: M9 Evidence (70-90s)

30 paired A/B trials / 60 arm executions.
Authority violations: 25 -> 0
Stale BEFORE execution: 0 -> 0
Cost overhead: -19% (cheaper)
SLA degradation: +10.9%

SAFETY: PASS | OPERATIONAL: PASS | AXIOM-1: SUPPORTED
(in controlled inference-scaling experiment)
