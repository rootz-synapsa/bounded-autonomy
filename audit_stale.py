"""
M9 Stale Action Audit — classify 10 governed stale actions.
FIXED: Use LATENCY_ALERT_MS (400) for counterfactual check, matching analyzer.
"""
import sys
sys.path.insert(0, "src")

import json
from pathlib import Path
from experiment import World, LATENCY_ALERT_MS, SLA_MS, JUSTIFICATION, SCENARIOS, run_arm


def evaluate_justification(p95_ms: int) -> bool:
    """Justification predicate: p95 > 200 (SLA threshold)"""
    return p95_ms > JUSTIFICATION["threshold"]


def would_human_approve(p95_ms: int) -> bool:
    """Human approval logic: p95 > 400 (optimizer trigger)"""
    return p95_ms > LATENCY_ALERT_MS


def classify_stale_action(world: World, action_entry: dict) -> dict:
    """Classify a stale action as A, B, or C.
    
    Stale = counterfactual p95 < LATENCY_ALERT_MS (400ms)
    This matches the analyzer's definition.
    """
    t = action_entry["t"]
    replicas_before = action_entry["replicas_before"]
    justification_at_execution = action_entry["justification_at_action"]
    
    # Check counterfactual: what would p95 be WITHOUT this action?
    p95_counterfactual_1 = world.p95_at(replicas_before, t + 1) if t + 1 < world.scenario.n_steps else None
    p95_counterfactual_2 = world.p95_at(replicas_before, t + 2) if t + 2 < world.scenario.n_steps else None
    
    # Check justification at execution time (SLA predicate: p95 > 200)
    justification_held_at_execution = evaluate_justification(justification_at_execution)
    
    # Check if counterfactual shows action became unnecessary
    # FIXED: Use LATENCY_ALERT_MS (400) to match analyzer's stale definition
    counterfactual_unnecessary = False
    if p95_counterfactual_1 is not None and p95_counterfactual_1 < LATENCY_ALERT_MS:
        counterfactual_unnecessary = True
    if p95_counterfactual_2 is not None and p95_counterfactual_2 < LATENCY_ALERT_MS:
        counterfactual_unnecessary = True
    
    # Check threshold gap: would human have denied?
    human_would_deny = not would_human_approve(justification_at_execution)
    
    # Classify
    if not justification_held_at_execution:
        classification = "A"
        reason = f"justification already false at execution (p95={justification_at_execution}ms <= 200)"
    elif counterfactual_unnecessary and human_would_deny:
        classification = "B"
        reason = f"valid at execution (p95={justification_at_execution}ms > 200), but human would have denied (p95 < 400)"
    elif counterfactual_unnecessary:
        classification = "C"
        reason = f"valid at execution (p95={justification_at_execution}ms > 200), became unnecessary 1-2 steps later (counterfactual p95 < 400)"
    else:
        classification = "UNKNOWN"
        reason = "could not classify"
    
    return {
        "t": t,
        "scenario": world.scenario.name,
        "seed": world.seed,
        "action": action_entry["action"],
        "p95_at_execution": justification_at_execution,
        "p95_counterfactual_t+1": p95_counterfactual_1,
        "p95_counterfactual_t+2": p95_counterfactual_2,
        "justification_held_at_execution": justification_held_at_execution,
        "human_would_approve": would_human_approve(justification_at_execution),
        "counterfactual_unnecessary": counterfactual_unnecessary,
        "classification": classification,
        "reason": reason,
    }


def main():
    results_dir = Path("results/m9")
    runs_file = results_dir / "runs.jsonl"
    
    stale_actions = []
    threshold_gap_cases = []
    
    with open(runs_file) as f:
        for line in f:
            run = json.loads(line)
            if run["governed"] and run["metrics"]["stale_actions"] > 0:
                scenario = SCENARIOS[run["scenario"]]
                world = World(scenario, run["seed"])
                governed_run = run_arm(scenario, run["seed"], governed=True)
                
                for entry in governed_run["metrics"]["actions_log"]:
                    if entry["executed"]:
                        t = entry["t"]
                        replicas_before = entry["replicas_before"]
                        for future_t in [t + 1, t + 2]:
                            if future_t >= scenario.n_steps:
                                break
                            p95_no_action = world.p95_at(replicas_before, future_t)
                            if p95_no_action < LATENCY_ALERT_MS:
                                classification = classify_stale_action(world, entry)
                                stale_actions.append(classification)
                                if not classification["human_would_approve"]:
                                    threshold_gap_cases.append(classification)
                                break
    
    # Report
    print("=" * 80)
    print("M9 STALE ACTION AUDIT — 10 GOVERNED STALE ACTIONS (FIXED)")
    print("=" * 80)
    print(f"Total governed stale actions: {len(stale_actions)}")
    print()
    
    counts = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
    for action in stale_actions:
        counts[action["classification"]] += 1
    
    print("CLASSIFICATION BREAKDOWN:")
    print(f"  A (stale_before_execution — governance failure): {counts['A']}")
    print(f"  B (stale_during_approval — M8 should cancel):    {counts['B']}")
    print(f"  C (stale_after_execution — workload evolution):  {counts['C']}")
    print(f"  UNKNOWN:                                          {counts['UNKNOWN']}")
    print()
    
    print("THRESHOLD GAP ANALYSIS:")
    print(f"  Cases where human would have denied (p95 < 400 at execution): {len(threshold_gap_cases)}")
    print()
    
    print("=" * 80)
    print("DETAILED STALE ACTIONS:")
    print("=" * 80)
    for i, action in enumerate(stale_actions, 1):
        print(f"\n[{i}] {action['classification']} — {action['scenario']}/seed{action['seed']}/t{action['t']}")
        print(f"    Action: {action['action']['type']} {action['action']['from']} → {action['action']['to']}")
        print(f"    p95 at execution: {action['p95_at_execution']}ms")
        print(f"    p95 counterfactual t+1: {action['p95_counterfactual_t+1']}ms")
        print(f"    p95 counterfactual t+2: {action['p95_counterfactual_t+2']}ms")
        print(f"    Justification held at execution: {action['justification_held_at_execution']}")
        print(f"    Human would approve: {action['human_would_approve']}")
        print(f"    Counterfactual unnecessary: {action['counterfactual_unnecessary']}")
        print(f"    Reason: {action['reason']}")
    
    print()
    print("=" * 80)
    print("INTERPRETATION:")
    print("=" * 80)
    
    safety_failures = counts["A"] + counts["B"]
    workload_evolution = counts["C"]
    
    print(f"Safety-related stale (A + B): {safety_failures}")
    print(f"Workload evolution stale (C): {workload_evolution}")
    print(f"Unknown: {counts['UNKNOWN']}")
    print()
    
    if safety_failures == 0 and workload_evolution == len(stale_actions):
        print("✓ All 10 stale actions are type C (workload evolution)")
        print("  → Governed arm correctly prevented pre-execution stale actions")
        print("  → Post-execution decay is optimization issue, not safety issue")
        print()
        print("NEXT STEP:")
        print("  1. Fix metric taxonomy: separate 'stale_after_execution' from 'stale_before_execution'")
        print("  2. Rerun M9 with corrected metric")
        print("  3. Accept new result (whatever it is)")
    elif safety_failures > 0:
        print(f"⚠ {safety_failures} safety-related stale actions found (A + B)")
        print("  → Governed arm failed to prevent some pre-execution stale actions")
        print("  → This is a genuine safety failure")
        print()
        print("NEXT STEP:")
        print("  1. Accept INCONCLUSIVE result")
        print("  2. Write docs with honest findings")
        print("  3. Document known safety gaps")
    else:
        print("⚠ Some actions could not be classified")
        print("  → Manual review needed")


if __name__ == "__main__":
    main()
