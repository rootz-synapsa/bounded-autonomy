"""
M9 runner: 30 A/B runs (3 scenarios x 10 seeds x 2 arms).
Writes results to results/m9/.
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

            # Counterfactual stale detection
            u_world = World(scenario, seed)
            g_world = World(scenario, seed)
            ungoverned["metrics"]["stale_actions"] = count_stale_actions(
                u_world, ungoverned["metrics"]["actions_log"])
            governed["metrics"]["stale_actions"] = count_stale_actions(
                g_world, governed["metrics"]["actions_log"])

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
    print("M9 EXPERIMENT RESULTS — 30 A/B RUNS")
    print("=" * 64)
    print(f"SAFETY VALUE:       {verdicts['safety_value']}")
    print(f"OPERATIONAL VALUE:  {verdicts['operational_value']}")
    print(f"AXIOM-1 SUPPORT:    {verdicts['axiom1_support']}")
    print("-" * 64)
    print(f"Authority violations: ungoverned={verdicts['total_ungoverned_authority_violations']}, "
          f"governed={verdicts['total_governed_authority_violations']}")
    print(f"Stale actions:        ungoverned={verdicts['total_ungoverned_stale_actions']}, "
          f"governed={verdicts['total_governed_stale_actions']}")
    print(f"Cost overhead:        {verdicts['cost_overhead_pct']}%")
    print(f"SLA degradation:      {verdicts['sla_degradation_pct']}%")
    print("=" * 64)
    print(f"Results written to: {results_dir}")


if __name__ == "__main__":
    main()
