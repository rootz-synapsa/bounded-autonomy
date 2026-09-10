from governance import evaluate_action, Verdict
from executor import execute
from logger import log_event

class BoundedExecutionEngine:
    """
    The core of Agent Flight Recorder.
    It NEVER executes an action without passing through the Governance Gate.
    """
    def __init__(self, policy: dict):
        self.policy = policy

    def process_intent(self, run_id: str, initial_state: dict, action: dict) -> dict:
        # Step 1: Intercept & Evaluate
        verdict, reason = evaluate_action(action, self.policy)
        
        # Step 2: Decide & Enforce (Fail-Closed)
        if verdict == Verdict.AUTHORIZED:
            execution_status = execute(action)
            # Simulate state change after successful execution
            final_state = {
                "t": initial_state["t"] + 1, 
                "replicas": action.get("to", initial_state["replicas"]), 
                "p95_ms": 176
            }
        else:
            # BLOCKED: State remains unchanged, execution is prevented
            execution_status = f"BLOCKED ({reason})"
            final_state = initial_state.copy()
            
        # Step 3: Preserve Evidence (Provenance Log)
        log_path = log_event(run_id, initial_state, action, execution_status, final_state, verdict.value)
        
        return {
            "verdict": verdict.value,
            "reason": reason,
            "execution_status": execution_status,
            "final_state": final_state,
            "evidence_log": str(log_path)
        }
