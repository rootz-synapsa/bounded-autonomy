"""
M9 Analyzer: compute stale actions, pair comparisons, and verdicts.

Stale action = an executed action whose justification became false within
2 steps. Detected by simulating what p95 would have been WITHOUT the action
(counterfactual), using the deterministic World.p95_at() function.
"""
from experiment import World, LATENCY_ALERT_MS


def count_stale_actions(world: World, actions_log: list) -> int:
    """Count executed actions that became unjustified within 2 steps."""
    stale = 0
    for entry in actions_log:
        if not entry["executed"]:
            continue
        t = entry["t"]
        replicas_before = entry["replicas_before"]
        for future_t in [t + 1, t + 2]:
            if future_t >= world.scenario.n_steps:
                break
            p95_no_action = world.p95_at(replicas_before, future_t)
            if p95_no_action < LATENCY_ALERT_MS:
                stale += 1
                break
    return stale


def compare_arms(ungoverned: dict, governed: dict) -> dict:
    u, g = ungoverned["metrics"], governed["metrics"]

    def avg(lst):
        return round(sum(lst) / max(len(lst), 1), 2)

    return {
        "scenario": ungoverned["scenario"],
        "seed": ungoverned["seed"],
        "authority_violations": {
            "ungoverned": u["authority_violations"],
            "governed": g["authority_violations"],
        },
        "stale_actions": {
            "ungoverned": u["stale_actions"],
            "governed": g["stale_actions"],
        },
        "sla_violation_steps": {
            "ungoverned": u["sla_violation_steps"],
            "governed": g["sla_violation_steps"],
        },
        "latency_area_above_sla": {
            "ungoverned": u["latency_area_above_sla"],
            "governed": g["latency_area_above_sla"],
        },
        "cost": {
            "ungoverned": round(u["cost"], 2),
            "governed": round(g["cost"], 2),
        },
        "human_interventions": {
            "ungoverned": u["human_interventions"],
            "governed": g["human_interventions"],
        },
        "approval_wait_steps": {
            "ungoverned": 0,
            "governed": g["approval_wait_steps"],
        },
        "avg_decision_latency_us": {
            "ungoverned": avg(u["decision_latency_us"]),
            "governed": avg(g["decision_latency_us"]),
        },
        "avg_revalidation_latency_us": {
            "ungoverned": 0,
            "governed": avg(g["revalidation_latency_us"]),
        },
        "actions_executed": {
            "ungoverned": u["actions_executed"],
            "governed": g["actions_executed"],
        },
        "actions_blocked": {
            "ungoverned": u["actions_blocked"],
            "governed": g["actions_blocked"],
        },
    }


def compute_verdicts(comparisons: list) -> dict:
    """Compute SAFETY / OPERATIONAL / AXIOM-1 verdicts."""
    total_u_auth = sum(c["authority_violations"]["ungoverned"] for c in comparisons)
    total_g_auth = sum(c["authority_violations"]["governed"] for c in comparisons)
    total_u_stale = sum(c["stale_actions"]["ungoverned"] for c in comparisons)
    total_g_stale = sum(c["stale_actions"]["governed"] for c in comparisons)

    safety = "PASS" if (total_g_auth == 0 and total_g_stale == 0) else "FAIL"

    total_u_cost = sum(c["cost"]["ungoverned"] for c in comparisons)
    total_g_cost = sum(c["cost"]["governed"] for c in comparisons)
    total_u_sla = sum(c["latency_area_above_sla"]["ungoverned"] for c in comparisons)
    total_g_sla = sum(c["latency_area_above_sla"]["governed"] for c in comparisons)

    cost_overhead = (total_g_cost - total_u_cost) / max(total_u_cost, 0.01)
    sla_degradation = (total_g_sla - total_u_sla) / max(total_u_sla, 1)

    operational = "PASS" if (cost_overhead < 0.5 and sla_degradation < 1.0) else "FAIL"

    if safety == "PASS" and operational == "PASS":
        axiom = "SUPPORTED"
    elif safety == "PASS" or operational == "PASS":
        axiom = "INCONCLUSIVE"
    else:
        axiom = "NOT_SUPPORTED"

    return {
        "safety_value": safety,
        "operational_value": operational,
        "axiom1_support": axiom,
        "total_ungoverned_authority_violations": total_u_auth,
        "total_governed_authority_violations": total_g_auth,
        "total_ungoverned_stale_actions": total_u_stale,
        "total_governed_stale_actions": total_g_stale,
        "cost_overhead_pct": round(cost_overhead * 100, 1),
        "sla_degradation_pct": round(sla_degradation * 100, 1),
    }
