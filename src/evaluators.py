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
    """Checks if action complies with operational policies (absolute limits).
    Policy violations are hard constraints that cannot be overridden."""
    def evaluate(self, action: dict, policy: dict) -> EvaluationResult:
        if action.get("type") == "SCALE_REPLICAS":
            # Absolute ceiling — never exceed regardless of authority
            absolute_max = policy.get("absolute_max_replicas", 10)
            requested = action.get("to", 0)
            if requested > absolute_max:
                return EvaluationResult(
                    passed=False,
                    reason=f"Exceeds absolute policy ceiling ({absolute_max})"
                )
        return EvaluationResult(passed=True, reason="Within policy bounds")


class AuthorityEvaluator:
    """Checks if agent has delegated authority (bounded envelope).
    
    Bounded authority model:
    - requested <= auto_scale_max → sufficient (proceed to AUTO if policy OK)
    - auto_scale_max < requested <= supervised_scale_max → insufficient (SUPERVISED)
    - requested > supervised_scale_max → outside envelope (should be caught by policy)
    
    This is NOT RBAC — it's a delegated envelope per agent instance.
    """
    def evaluate(self, action: dict, agent_context: dict) -> EvaluationResult:
        action_type = action.get("type")
        if action_type != "SCALE_REPLICAS":
            return EvaluationResult(passed=True, reason="Non-scaling action")
        
        requested = action.get("to", 0)
        authority = agent_context.get("authority", {})
        auto_max = authority.get("auto_scale_max", 6)
        supervised_max = authority.get("supervised_scale_max", 10)
        
        if requested <= auto_max:
            return EvaluationResult(
                passed=True,
                reason=f"Within autonomous envelope (≤{auto_max})"
            )
        elif requested <= supervised_max:
            return EvaluationResult(
                passed=False,
                reason=f"Exceeds autonomous envelope ({auto_max}), requires supervision (≤{supervised_max})"
            )
        else:
            # Should be caught by policy, but defensive check
            return EvaluationResult(
                passed=False,
                reason=f"Outside agent's delegated envelope ({supervised_max})"
            )


class InvariantEvaluator:
    """Checks if action violates system invariants (fail-closed).
    Invariant violations always result in BLOCK, never SUPERVISED."""
    FORBIDDEN_ACTIONS = {"DROP_DATABASE", "DELETE_PRODUCTION", "WIPE_LOGS"}
    
    def evaluate(self, action: dict, state: dict) -> EvaluationResult:
        action_type = action.get("type")
        if action_type in self.FORBIDDEN_ACTIONS:
            return EvaluationResult(
                passed=False,
                reason=f"Invariant violation: '{action_type}' is forbidden"
            )
        # M8: state-based invariant (maintenance freeze blocks scaling)
        if action_type == "SCALE_REPLICAS" and state.get("maintenance_freeze"):
            return EvaluationResult(
                passed=False,
                reason="Invariant violation: maintenance freeze active"
            )
        return EvaluationResult(passed=True, reason="No invariant violations")
