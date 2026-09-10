"""
M9 runner: 30 A/B runs (3 scenarios x 10 seeds x 2 arms).
CORRECTED: Uses separated stale_before_execution / stale_after_execution metrics.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from experiment import SCENARIOS, run_arm, World
from analyzer import count_stale_actions, compare_arms, compute_verdicts


def main():
    all_runs = []
    comparisons = []

    for scenario_name, scenario in SCENARIOS.items():
        for seed in range(10):
            ungoverned = run_arm(scenario, seed, governed=False)
            governed = run_arm(scenario, seed, governed=True)

            # Counterfactual stale detection (corrected taxonomy)
            u_world = World(scenario, seed)
            g_world = World(scenario, seed)
            
            u_stale = count_stale_actions(u_world, ungoverned["metrics"]["actions_log"])
            g_stale = count_stale_actions(g_world, governed["metrics"]["actions_log"])
            
            ungoverned["metrics"]["stale_before_execution"] = u_stale["before_execution"]
            ungoverned["metrics"]["stale_after_execution"] = u_stale["after_execution"]
            governed["metrics"]["stale_before_execution"] = g_stale["before_execution"]
            governed["metrics"]["stale_after_execution"] = g_stale["after_execution"]

            all_runs.append(ungoverned)
            all_runs.append(governed)
            comparisons.append(compare_arms(ungoverned, governed))

    verdicts = compute_verdicts(comparisons)

    results_dir = Path(__file__).parent.parent / "results" / "m9"
    results_dir.mkdir(parents=True, exist_ok=True)

    with open(results_dir / "runs.jsonl", "w") as f:
        for run in all_runs:
            f.write(json.dumps({
                "scenario": run["scenario"],
                "seed": run["seed"],
                "governed": run["governed"],
                "metrics": {k: v for k, v in run["metrics"].items()
                            if k != "actions_log"},
                "trajectory": run["trajectory"],
            }) + "\n")

    with open(results_dir / "comparisons.jsonl", "w") as f:
        for c in comparisons:
            f.write(json.dumps(c) + "\n")

    with open(results_dir / "verdicts.json", "w") as f:
        json.dump(verdicts, f, indent=2)

    print("=" * 64)
    print("M9 EXPERIMENT RESULTS — 30 A/B RUNS (CORRECTED METRICS)")
    print("=" * 64)
    print(f"SAFETY VALUE:       {verdicts['safety_value']}")
    print(f"OPERATIONAL VALUE:  {verdicts['operational_value']}")
    print(f"AXIOM-1 SUPPORT:    {verdicts['axiom1_support']}")
    print("-" * 64)
    print(f"Authority violations:     ungoverned={verdicts['total_ungoverned_authority_violations']}, "
          f"governed={verdicts['total_governed_authority_violations']}")
    print(f"Stale BEFORE execution:   ungoverned={verdicts['total_ungoverned_stale_before_execution']}, "
          f"governed={verdicts['total_governed_stale_before_execution']}")
    print(f"Stale AFTER execution:    ungoverned={verdicts['total_ungoverned_stale_after_execution']}, "
          f"governed={verdicts['total_governed_stale_after_execution']}")
    print(f"Cost overhead:            {verdicts['cost_overhead_pct']}%")
    print(f"SLA degradation:          {verdicts['sla_degradation_pct']}%")
    print("=" * 64)
    print(f"Results written to: {results_dir}")
    print()
    print("NOTE: This is a MEASUREMENT CORRECTION, not threshold tuning.")
    print("      stale_before_execution = safety issue (governance failure)")
    print("      stale_after_execution = optimization issue (workload evolution)")


if __name__ == "__main__":
    main()
