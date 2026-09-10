"""
M8 Revalidation Execution Gate.

GRANTED is not enough — authority is valid only while reality remains valid.
Every check must pass against the CURRENT state, not the state at grant time.
"""
import json
import hashlib
from dataclasses import dataclass, field
from authorization import AuthorizationStatus, action_key, state_hash


def evaluate_predicate(predicate: dict, state: dict) -> bool:
    """Evaluate an objective-binding predicate against current state.
    predicate = {"metric": "p95_ms", "operator": ">", "threshold": 200}
    """
    metric_name = predicate.get("metric")
    threshold = predicate.get("threshold")
    operator = predicate.get("operator", ">")
    current_value = state.get(metric_name)
    if current_value is None:
        return False
    ops = {
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
    }
    return ops.get(operator, lambda a, b: False)(current_value, threshold)


@dataclass
class RevalidationCheck:
    name: str
    passed: bool
    reason: str


@dataclass
class RevalidationResult:
    passed: bool
    checks: list = field(default_factory=list)

    @property
    def failed_reason(self) -> str:
        failures = [c.reason for c in self.checks if not c.passed]
        return "; ".join(failures)


class RevalidationGate:
    """Revalidates a GRANTED authorization against current reality."""

    def __init__(self, decision_engine):
        self.decision_engine = decision_engine

    def revalidate(self, auth, action: dict, state: dict,
                   policy: dict, agent_context: dict) -> RevalidationResult:
        checks = []

        # 1. Action binding: must be the exact action that was approved
        if action_key(action) != action_key(auth.action):
            checks.append(RevalidationCheck(
                "action_binding", False,
                "action differs from the approved action"))
        else:
            checks.append(RevalidationCheck(
                "action_binding", True, "action matches grant-time action"))

        # 2. Objective binding: justification predicate must still hold
        if auth.context_predicate is not None:
            if evaluate_predicate(auth.context_predicate, state):
                checks.append(RevalidationCheck(
                    "objective_binding", True,
                    f"justification holds: {auth.context_predicate['metric']} "
                    f"{auth.context_predicate['operator']} {auth.context_predicate['threshold']}"))
            else:
                checks.append(RevalidationCheck(
                    "objective_binding", False,
                    f"justification no longer holds: {auth.context_predicate['metric']} "
                    f"= {state.get(auth.context_predicate['metric'])} "
                    f"(predicate {auth.context_predicate['operator']} "
                    f"{auth.context_predicate['threshold']} is false)"))

        # 3. State binding: state must match grant-time snapshot
        if auth.state_hash_at_grant is not None:
            if state_hash(state) == auth.state_hash_at_grant:
                checks.append(RevalidationCheck(
                    "state_binding", True, "state matches grant-time snapshot"))
            else:
                checks.append(RevalidationCheck(
                    "state_binding", False, "state drifted since grant"))

        # 4. Invariant + 5. Policy/Authority still valid: re-run all evaluators
        verdict, reason = self.decision_engine.evaluate(
            action, policy, agent_context, state)

        if verdict.value == "BLOCK":
            checks.append(RevalidationCheck(
                "invariant_policy_authority", False,
                f"evaluators no longer pass: {reason}"))
        else:
            checks.append(RevalidationCheck(
                "invariant_policy_authority", True,
                "invariant, policy, and authority still valid"))

        passed = all(c.passed for c in checks)
        return RevalidationResult(passed=passed, checks=checks)
