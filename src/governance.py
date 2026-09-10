"""
DecisionEngine: synthesizes 3 evaluator results into a verdict.
Verdict taxonomy: AUTO / SUPERVISED / BLOCK / UNGOVERNED
"""
from enum import Enum
from evaluators import PolicyEvaluator, AuthorityEvaluator, InvariantEvaluator


class Verdict(Enum):
    AUTO = "AUTO"              # All checks pass → execute automatically
    SUPERVISED = "SUPERVISED"  # Policy pass, authority insufficient → await bounded approval
    BLOCK = "BLOCK"            # Invariant violation or policy fail → fail-closed
    UNGOVERNED = "UNGOVERNED"  # H0 baseline: no governance applied


class DecisionEngine:
    """
    Synthesizes 3 evaluators into a single verdict.
    Priority: Invariant > Authority > Policy
    """
    def __init__(self):
        self.policy_eval = PolicyEvaluator()
        self.authority_eval = AuthorityEvaluator()
        self.invariant_eval = InvariantEvaluator()
    
    def evaluate(self, action: dict, policy: dict, agent_context: dict, state: dict) -> tuple[Verdict, str]:
        # Invariant first — violations always BLOCK
        invariant_result = self.invariant_eval.evaluate(action, state)
        if not invariant_result.passed:
            return Verdict.BLOCK, invariant_result.reason
        
        # Authority second — insufficient authority → SUPERVISED
        authority_result = self.authority_eval.evaluate(action, agent_context)
        
        # Policy third — policy fail → BLOCK
        policy_result = self.policy_eval.evaluate(action, policy)
        if not policy_result.passed:
            return Verdict.BLOCK, policy_result.reason
        
        # If authority insufficient but policy+invariant pass → SUPERVISED
        if not authority_result.passed:
            return Verdict.SUPERVISED, authority_result.reason
        
        # All pass → AUTO
        return Verdict.AUTO, "All evaluations passed"
