"""
M9 Analyzer: compute stale actions, pair comparisons, and verdicts.

CORRECTED METRIC TAXONOMY:
- stale_before_execution: justification was false at execution time → SAFETY issue
- stale_after_execution: valid at execution, became unnecessary 1-2 steps later → OPTIMIZATION issue

Only stale_before_execution counts toward SAFETY verdict.
"""
from experiment import World, LATENCY_ALERT_MS, JUSTIFICATION


def evaluate_justification(p95_ms: int) -> bool:
    """Justification predicate: p95 > 200 (SLA threshold)"""
    return p95_ms > JUSTIFICATION["threshold"]


def count_stale_actions(world: World, actions_log: list) -> dict:
    """Count stale actions, separated by type.
    
    Returns:
        {
            "total": int,
            "before_execution": int,  # safety issue
            "after_execution": int,   # optimization issue
        }
    """
    before_execution = 0
    after_execution = 0
    
    for entry in actions_log:
        if not entry["executed"]:
            continue
        t = entry["t"]
        replicas_before = entry["replicas_before"]
        justification_at_execution = entry["justification_at_action"]
        
        # Check if action became unnecessary within 2 steps
        became_unnecessary = False
        for future_t in [t + 1, t + 2]:
            if future_t >= world.scenario.n_steps:
                break
            p95_no_action = world.p95_at(replicas_before, future_t)
            if p95_no_action < LATENCY_ALERT_MS:
                became_unnecessary = True
                break
        
        if not became_unnecessary:
            continue
        
        # Classify: was justification valid at execution time?
        if not evaluate_justification(justification_at_execution):
            # Justification was already false at execution → safety issue
            before_execution += 1
        else:
            # Justification was valid at execution, became unnecessary later → optimization
            after_execution += 1
    
    return {
        "total": before_execution + after_execution,
        "before_execution": before_execution,
        "after_execution": after_execution,
    }


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
        "stale_before_execution": {
            "ungoverned": u["stale_before_execution"],
            "governed": g["stale_before_execution"],
        },
        "stale_after_execution": {
            "ungoverned": u["stale_after_execution"],
            "governed": g["stale_after_execution"],
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
    """Compute SAFETY / OPERATIONAL / AXIOM-1 verdicts.
    
    CORRECTED: Safety uses stale_before_execution only (not total stale).
    """
    total_u_auth = sum(c["authority_violations"]["ungoverned"] for c in comparisons)
    total_g_auth = sum(c["authority_violations"]["governed"] for c in comparisons)
    total_u_stale_before = sum(c["stale_before_execution"]["ungoverned"] for c in comparisons)
    total_g_stale_before = sum(c["stale_before_execution"]["governed"] for c in comparisons)
    total_u_stale_after = sum(c["stale_after_execution"]["ungoverned"] for c in comparisons)
    total_g_stale_after = sum(c["stale_after_execution"]["governed"] for c in comparisons)

    # SAFETY: only stale_before_execution counts (governance failure)
    safety = "PASS" if (total_g_auth == 0 and total_g_stale_before == 0) else "FAIL"

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
        "total_ungoverned_stale_before_execution": total_u_stale_before,
        "total_governed_stale_before_execution": total_g_stale_before,
        "total_ungoverned_stale_after_execution": total_u_stale_after,
        "total_governed_stale_after_execution": total_g_stale_after,
        "cost_overhead_pct": round(cost_overhead * 100, 1),
        "sla_degradation_pct": round(sla_degradation * 100, 1),
    }
