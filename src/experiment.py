"""
M9 Experiment Runner: 30 A/B runs (3 scenarios x 10 seeds x 2 arms).
Controlled experiment: H0 (ungoverned) vs H1 (governed).
Same workload, same optimizer, same seed, same initial state, same cost model.
Only difference: governance path.
"""
import random
import time
from dataclasses import dataclass
from authorization import AuthorizationManager
from engine import BoundedExecutionEngine


SLA_MS = 200
COST_PER_REPLICA = 0.10
AUTH_TTL_STEPS = 3
LATENCY_ALERT_MS = 400
JUSTIFICATION = {"metric": "p95_ms", "operator": ">", "threshold": 200}
POLICY = {"absolute_max_replicas": 10}
AGENT = {
    "actor_id": "inference-autopilot",
    "authority": {"auto_scale_max": 6, "supervised_scale_max": 10},
}


@dataclass
class Scenario:
    name: str
    workload: list
    initial_replicas: int
    n_steps: int


SCENARIOS = {
    "spike": Scenario(
        name="spike",
        workload=[1.0, 1.0, 3.5, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 1.0],
        initial_replicas=4,
        n_steps=10,
    ),
    "overshoot": Scenario(
        name="overshoot",
        workload=[1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 3.2],
        initial_replicas=2,
        n_steps=10,
    ),
    "stale_approval": Scenario(
        name="stale_approval",
        workload=[1.0, 1.2, 4.8, 1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        initial_replicas=4,
        n_steps=10,
    ),
}


class World:
    """Discrete-time world with responsive latency and cost."""

    def __init__(self, scenario: Scenario, seed: int):
        self.scenario = scenario
        self.seed = seed
        self.replicas = scenario.initial_replicas

    def load_at(self, t: int) -> float:
        w = self.scenario.workload
        return w[t] if t < len(w) else w[-1]

    def p95_at(self, replicas: int, t: int) -> int:
        """Pure function: same (seed, replicas, t) always yields same p95."""
        load = self.load_at(t)
        rng_step = random.Random(self.seed * 10000 + t)
        noise = rng_step.uniform(-10, 10)
        return max(50, int(500 * load / replicas + noise))


def propose_action(state: dict):
    """Same optimizer for both arms (controlled variable)."""
    if state["p95_ms"] > LATENCY_ALERT_MS and state["replicas"] < 12:
        return {
            "type": "SCALE_REPLICAS",
            "from": state["replicas"],
            "to": min(state["replicas"] * 2, 12),
            "reason": "high_latency",
        }
    return None


def run_arm(scenario: Scenario, seed: int, governed: bool) -> dict:
    """Run one arm (H0 ungoverned or H1 governed) through the scenario."""
    world = World(scenario, seed)

    m = {
        "authority_violations": 0,
        "stale_actions": 0,
        "sla_violation_steps": 0,
        "latency_area_above_sla": 0,
        "cost": 0.0,
        "approval_wait_steps": 0,
        "human_interventions": 0,
        "actions_executed": 0,
        "actions_blocked": 0,
        "actions_supervised": 0,
        "decision_latency_us": [],
        "revalidation_latency_us": [],
        "sla_recovery_steps": None,
        "actions_log": [],
    }

    if governed:
        manager = AuthorizationManager(clock=lambda: world.t,
                                       default_ttl_seconds=AUTH_TTL_STEPS)
        engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=manager)
        pending = []

    sla_breached_at = None
    trajectory = []

    for t in range(scenario.n_steps):
        world.t = t  # expose timestep for AuthorizationManager clock
        state = {"t": t, "replicas": world.replicas,
                 "p95_ms": world.p95_at(world.replicas, t)}

        # Track SLA
        if state["p95_ms"] > SLA_MS:
            m["sla_violation_steps"] += 1
            m["latency_area_above_sla"] += state["p95_ms"] - SLA_MS
            if sla_breached_at is None:
                sla_breached_at = t
        else:
            if sla_breached_at is not None and m["sla_recovery_steps"] is None:
                m["sla_recovery_steps"] = t - sla_breached_at

        # Process pending approvals (governed arm)
        action_executed_this_step = False
        executed_action = None

        if governed and pending:
            for (auth_id, action, requested_at) in pending:
                m["approval_wait_steps"] += 1
                if state["p95_ms"] > LATENCY_ALERT_MS:
                    # Human approves — justification still holds
                    m["human_interventions"] += 1
                    t0 = time.perf_counter()
                    try:
                        manager.grant(auth_id, "human-ops-1", state,
                                      context_predicate=JUSTIFICATION)
                    except ValueError:
                        m["revalidation_latency_us"].append(
                            (time.perf_counter() - t0) * 1e6)
                        continue
                    m["decision_latency_us"].append(
                        (time.perf_counter() - t0) * 1e6)
                    t1 = time.perf_counter()
                    result = engine.execute_with_revalidation(
                        f"RUN-{scenario.name}-s{seed}-t{t}",
                        state, action, auth_id)
                    m["revalidation_latency_us"].append(
                        (time.perf_counter() - t1) * 1e6)

                    if result["execution"] == "EXECUTED_SUCCESS":
                        m["actions_executed"] += 1
                        action_executed_this_step = True
                        executed_action = action
                        m["actions_log"].append({
                            "t": t, "action": action, "executed": True,
                            "replicas_before": action["from"],
                            "justification_at_action": state["p95_ms"],
                        })
                    else:
                        m["actions_blocked"] += 1
                        m["actions_log"].append({
                            "t": t, "action": action, "executed": False,
                            "replicas_before": action["from"],
                            "justification_at_action": state["p95_ms"],
                            "blocked_reason": result["execution"],
                        })
                else:
                    # Human denies — justification no longer holds
                    m["human_interventions"] += 1
                    m["actions_blocked"] += 1
                    m["actions_log"].append({
                        "t": t, "action": action, "executed": False,
                        "replicas_before": action["from"],
                        "justification_at_action": state["p95_ms"],
                        "blocked_reason": "denied_by_human",
                    })
                    try:
                        manager.deny(auth_id, "human-ops-1",
                                     "justification no longer holds")
                    except ValueError:
                        pass
            pending = []

        # Propose new action
        action = propose_action(state)
        if action and not action_executed_this_step:
            if governed:
                t0 = time.perf_counter()
                result = engine.process_intent(
                    f"RUN-{scenario.name}-s{seed}-t{t}", state, action)
                m["decision_latency_us"].append(
                    (time.perf_counter() - t0) * 1e6)

                if result["decision"] == "AUTO":
                    m["actions_executed"] += 1
                    action_executed_this_step = True
                    executed_action = action
                    m["actions_log"].append({
                        "t": t, "action": action, "executed": True,
                        "replicas_before": action["from"],
                        "justification_at_action": state["p95_ms"],
                    })
                elif result["decision"] == "SUPERVISED":
                    m["actions_supervised"] += 1
                    pending.append((result["authorization_id"], action, t))
                else:
                    m["actions_blocked"] += 1
                    m["authority_violations"] += 1
                    m["actions_log"].append({
                        "t": t, "action": action, "executed": False,
                        "replicas_before": action["from"],
                        "justification_at_action": state["p95_ms"],
                        "blocked_reason": result["execution"],
                    })
            else:
                # Ungoverned: execute immediately
                m["actions_executed"] += 1
                action_executed_this_step = True
                executed_action = action
                if action["to"] > AGENT["authority"]["auto_scale_max"]:
                    m["authority_violations"] += 1
                m["actions_log"].append({
                    "t": t, "action": action, "executed": True,
                    "replicas_before": action["from"],
                    "justification_at_action": state["p95_ms"],
                })

        # World advances
        m["cost"] += world.replicas * COST_PER_REPLICA
        if action_executed_this_step and executed_action:
            world.replicas = executed_action["to"]

        trajectory.append({
            "t": t,
            "replicas": world.replicas,
            "p95_ms": state["p95_ms"],
            "load": world.load_at(t),
        })

    return {
        "scenario": scenario.name,
        "seed": seed,
        "governed": governed,
        "metrics": m,
        "trajectory": trajectory,
    }
