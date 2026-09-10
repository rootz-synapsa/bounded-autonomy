"""
Three independent evaluators for the governed H1 path.
Each returns (passed: bool, reason: str).
"""

from dataclasses import dataclass

@dataclass
class EvaluationResult:
    passed: bool
    reason: str


class PolicyEvaluator:
    """Checks if action complies with operational policies."""
    def evaluate(self, action: dict, policy: dict) -> EvaluationResult:
        if action.get("type") == "SCALE_REPLICAS":
            max_replicas = policy.get("max_replicas", 6)
            if action.get("to", 0) > max_replicas:
                return EvaluationResult(
                    passed=False,
                    reason=f"Exceeds max replicas policy ({max_replicas})"
                )
        return EvaluationResult(passed=True, reason="Within policy bounds")


class AuthorityEvaluator:
    """Checks if agent has authority to perform this action.
    If action requires elevated authority, returns passed=False
    to signal SUPERVISED (awaiting bounded approval).
    """
    ELEVATED_ACTIONS = {"DELETE_RESOURCE", "MODIFY_SECURITY", "SCALE_REPLICAS"}
    
    def evaluate(self, action: dict, agent_context: dict) -> EvaluationResult:
        action_type = action.get("type")
        if action_type in self.ELEVATED_ACTIONS:
            agent_role = agent_context.get("role", "observer")
            if agent_role != "admin":
                return EvaluationResult(
                    passed=False,
                    reason=f"Action '{action_type}' requires admin role (agent has '{agent_role}')"
                )
        return EvaluationResult(passed=True, reason="Authority sufficient")


class InvariantEvaluator:
    """Checks if action violates system invariants (fail-closed).
    Invariant violations always result in BLOCK, never SUPERVISED.
    """
    FORBIDDEN_ACTIONS = {"DROP_DATABASE", "DELETE_PRODUCTION", "WIPE_LOGS"}
    
    def evaluate(self, action: dict, state: dict) -> EvaluationResult:
        action_type = action.get("type")
        if action_type in self.FORBIDDEN_ACTIONS:
            return EvaluationResult(
                passed=False,
                reason=f"Invariant violation: '{action_type}' is forbidden"
            )
        return EvaluationResult(passed=True, reason="No invariant violations")
