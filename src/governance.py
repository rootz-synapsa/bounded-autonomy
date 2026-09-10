"""
DecisionEngine: synthesizes 3 evaluator results into a verdict.
Verdict taxonomy: AUTO / SUPERVISED / BLOCK / UNGOVERNED

Decision precedence:
1. Invariant violation -> BLOCK
2. Policy violation -> BLOCK
3. Insufficient delegated authority -> SUPERVISED
4. All checks pass -> AUTO

Human approval cannot override invariants or hard policy constraints.
"""
from enum import Enum
from evaluators import PolicyEvaluator, AuthorityEvaluator, InvariantEvaluator


class Verdict(Enum):
    AUTO = "AUTO"              # All checks pass → execute automatically
    SUPERVISED = "SUPERVISED"  # Policy+invariant OK, authority insufficient → await bounded approval
    BLOCK = "BLOCK"            # Invariant or policy fail → fail-closed (no override)
    UNGOVERNED = "UNGOVERNED"  # H0 baseline: no governance applied


class DecisionEngine:
    """
    Synthesizes 3 evaluators into a single verdict.
    
    Decision precedence (matches behavior, not RBAC):
    1. Invariant violation -> BLOCK
    2. Policy violation -> BLOCK
    3. Insufficient delegated authority -> SUPERVISED
    4. All checks pass -> AUTO
    """
    def __init__(self):
        self.policy_eval = PolicyEvaluator()
        self.authority_eval = AuthorityEvaluator()
        self.invariant_eval = InvariantEvaluator()
    
    def evaluate(self, action: dict, policy: dict, agent_context: dict, state: dict) -> tuple[Verdict, str]:
        # 1. Invariant first — violations always BLOCK
        invariant_result = self.invariant_eval.evaluate(action, state)
        if not invariant_result.passed:
            return Verdict.BLOCK, invariant_result.reason
        
        # 2. Policy second — violations always BLOCK (no human override)
        policy_result = self.policy_eval.evaluate(action, policy)
        if not policy_result.passed:
            return Verdict.BLOCK, policy_result.reason
        
        # 3. Authority third — insufficient → SUPERVISED (bounded approval)
        authority_result = self.authority_eval.evaluate(action, agent_context)
        if not authority_result.passed:
            return Verdict.SUPERVISED, authority_result.reason
        
        # 4. All pass → AUTO
        return Verdict.AUTO, "All evaluations passed"
