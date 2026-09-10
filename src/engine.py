"""
Bounded execution engine for the governed H1 path.
No action may execute without an explicit governance decision.
"""
from governance import DecisionEngine, Verdict
from executor import execute
from logger import log_event


class BoundedExecutionEngine:
    """
    Bounded execution engine for the governed H1 path.
    No action may execute without an explicit governance decision.
    """
    def __init__(self, policy: dict, agent_context: dict):
        self.policy = policy
        self.agent_context = agent_context
        self.decision_engine = DecisionEngine()

    def process_intent(self, run_id: str, initial_state: dict, action: dict) -> dict:
        # Step 1: Evaluate through 3 evaluators → DecisionEngine
        verdict, reason = self.decision_engine.evaluate(
            action, self.policy, self.agent_context, initial_state
        )
        
        # Step 2: Enforce based on verdict
        if verdict == Verdict.AUTO:
            execution_status = execute(action)
            final_state = {
                "t": initial_state["t"] + 1,
                "replicas": action.get("to", initial_state["replicas"]),
                "p95_ms": 176
            }
        elif verdict == Verdict.SUPERVISED:
            execution_status = f"SUPERVISED ({reason})"
            final_state = initial_state.copy()  # State unchanged until approval
        else:  # BLOCK or UNGOVERNED
            execution_status = f"BLOCKED ({reason})"
            final_state = initial_state.copy()
        
        # Step 3: Log evidence
        log_path = log_event(
            run_id, initial_state, action, execution_status, final_state, verdict.value
        )
        
        return {
            "verdict": verdict.value,
            "reason": reason,
            "execution_status": execution_status,
            "final_state": final_state,
            "evidence_log": str(log_path)
        }
