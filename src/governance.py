from enum import Enum

class Verdict(Enum):
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    HALTED = "HALTED"  # Fail-Closed default

def evaluate_action(action: dict, policy: dict) -> tuple[Verdict, str]:
    """
    The Decision Boundary.
    Separates what the agent WANTS to do from what it CAN do.
    """
    try:
        # Example Axiom: Do not allow scaling beyond 6 replicas in this environment
        if action.get("type") == "SCALE_REPLICAS":
            if action.get("to", 0) > policy.get("max_replicas", 6):
                return Verdict.DENIED, f"Exceeds maximum replica limit ({policy.get('max_replicas')})"
        
        # Default: If no rules broken, authorize
        return Verdict.AUTHORIZED, "Within policy bounds"
        
    except Exception as e:
        # INVARIANT: Conflict/Error -> halt & report (Fail-Closed)
        return Verdict.HALTED, f"Policy evaluation error: {str(e)}"
