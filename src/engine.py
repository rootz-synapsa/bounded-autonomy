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
    def __init__(self, policy: dict, agent_context: dict, authorization_manager=None):
        self.policy = policy
        self.agent_context = agent_context
        self.decision_engine = DecisionEngine()
        self.authorization_manager = authorization_manager

    def process_intent(self, run_id: str, initial_state: dict, action: dict) -> dict:
        verdict, reason = self.decision_engine.evaluate(
            action, self.policy, self.agent_context, initial_state
        )

        authorization_id = None
        if verdict == Verdict.AUTO:
            execution_status = execute(action)
            final_state = {
                "t": initial_state["t"] + 1,
                "replicas": action.get("to", initial_state["replicas"]),
                "p95_ms": 176
            }
        elif verdict == Verdict.SUPERVISED:
            execution_status = f"SUPERVISED ({reason})"
            final_state = initial_state.copy()
            if self.authorization_manager is not None:
                authorization_id = self.authorization_manager.request(action).authorization_id
        else:
            execution_status = f"BLOCKED ({reason})"
            final_state = initial_state.copy()

        log_path = log_event(
            run_id, initial_state, action, execution_status, final_state,
            verdict.value, authorization_id=authorization_id
        )

        return {
            "verdict": verdict.value,
            "reason": reason,
            "execution_status": execution_status,
            "final_state": final_state,
            "evidence_log": str(log_path),
            "authorization_id": authorization_id,
        }

    def execute_authorized(self, run_id: str, current_state: dict, action: dict,
                           authorization_id: str) -> dict:
        """
        M7 bounded approval: consume a GRANTED authorization to execute the exact
        action it was granted for, against the exact state it was granted against.
        Fail-closed on any lifecycle mismatch.
        """
        if self.authorization_manager is None:
            raise PermissionError("no authorization manager configured")

        try:
            auth = self.authorization_manager.consume(authorization_id, action, current_state)
            auth_status = auth.status.value
        except PermissionError as e:
            auth = self.authorization_manager.get(authorization_id)
            auth_status = auth.status.value if auth else "UNKNOWN"
            execution_status = f"BLOCKED (authorization: {e})"
            log_path = log_event(
                run_id, current_state, action, execution_status, current_state.copy(),
                Verdict.BLOCK.value, authorization_id=authorization_id
            )
            return {
                "verdict": Verdict.BLOCK.value,
                "reason": str(e),
                "execution_status": execution_status,
                "final_state": current_state.copy(),
                "evidence_log": str(log_path),
                "authorization_id": authorization_id,
                "authorization_status": auth_status,
            }

        execution_status = "EXECUTED_UNDER_AUTHORIZATION"
        new_state = {
            "t": current_state["t"] + 1,
            "replicas": action.get("to", current_state["replicas"]),
            "p95_ms": 176
        }
        log_path = log_event(
            run_id, current_state, action, execution_status, new_state,
            Verdict.SUPERVISED.value, authorization_id=authorization_id
        )
        return {
            "verdict": Verdict.SUPERVISED.value,
            "reason": "executed under granted bounded authorization",
            "execution_status": execution_status,
            "final_state": new_state,
            "evidence_log": str(log_path),
            "authorization_id": authorization_id,
            "authorization_status": auth_status,
        }
