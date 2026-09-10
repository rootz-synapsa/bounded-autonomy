"""
Bounded execution engine for the governed H1 path.
No action may execute without an explicit governance decision.
M8: GRANTED is not enough — revalidate against current reality before execute.

Three separate axes (never conflated):
- Decision:      AUTO | SUPERVISED | BLOCK
- Authorization: NOT_REQUIRED | PENDING | GRANTED | EXPIRED | INVALIDATED | CONSUMED
- Execution:     NOT_ATTEMPTED | EXECUTED_SUCCESS | EXECUTED_FAILED |
                 CANCELLED_AFTER_REVALIDATION | UNKNOWN
"""
from enum import Enum
from governance import DecisionEngine, Verdict
from authorization import AuthorizationStatus
from revalidation import RevalidationGate
from executor import execute
from logger import log_event


class ExecutionStatus(Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    EXECUTED_SUCCESS = "EXECUTED_SUCCESS"
    EXECUTED_FAILED = "EXECUTED_FAILED"
    CANCELLED_AFTER_REVALIDATION = "CANCELLED_AFTER_REVALIDATION"
    UNKNOWN = "UNKNOWN"


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
        self.revalidation_gate = RevalidationGate(self.decision_engine)

    def process_intent(self, run_id: str, initial_state: dict, action: dict) -> dict:
        verdict, reason = self.decision_engine.evaluate(
            action, self.policy, self.agent_context, initial_state
        )

        authorization_id = None
        authorization_axis = AuthorizationStatus.NOT_REQUIRED.value
        execution_axis = ExecutionStatus.NOT_ATTEMPTED.value

        if verdict == Verdict.AUTO:
            execution_status = execute(action)
            execution_axis = ExecutionStatus.EXECUTED_SUCCESS.value
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
                authorization_axis = AuthorizationStatus.PENDING.value
        else:
            execution_status = f"BLOCKED ({reason})"
            final_state = initial_state.copy()

        axes = {
            "decision": verdict.value,
            "authorization": authorization_axis,
            "execution": execution_axis,
        }
        log_path = log_event(
            run_id, initial_state, action, execution_status, final_state,
            verdict.value, authorization_id=authorization_id, axes=axes
        )

        return {
            "verdict": verdict.value,
            "reason": reason,
            "execution_status": execution_status,
            "final_state": final_state,
            "evidence_log": str(log_path),
            "authorization_id": authorization_id,
            # M8: three separate axes
            "decision": verdict.value,
            "authorization": authorization_axis,
            "execution": execution_axis,
        }

    def execute_authorized(self, run_id: str, current_state: dict, action: dict,
                           authorization_id: str) -> dict:
        """M7 bounded approval: consume a GRANTED authorization (legacy path)."""
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

    def execute_with_revalidation(self, run_id: str, current_state: dict, action: dict,
                                  authorization_id: str) -> dict:
        """
        M8 Revalidation Execution Gate.
        GRANTED is not enough — revalidate against current reality before execute.

        Returns three separate axes: decision / authorization / execution.
        """
        if self.authorization_manager is None:
            raise PermissionError("no authorization manager configured")

        auth = self.authorization_manager.get(authorization_id)
        if auth is None:
            raise PermissionError(f"unknown authorization: {authorization_id}")

        # Refresh TTL before revalidation
        self.authorization_manager._refresh_expiry(auth)

        # Path 1: TTL expired before revalidation → NOT_ATTEMPTED
        if auth.status == AuthorizationStatus.EXPIRED:
            execution_status = "NOT_ATTEMPTED (authorization expired before revalidation)"
            axes = {
                "decision": Verdict.SUPERVISED.value,
                "authorization": AuthorizationStatus.EXPIRED.value,
                "execution": ExecutionStatus.NOT_ATTEMPTED.value,
            }
            log_path = log_event(
                run_id, current_state, action, execution_status, current_state.copy(),
                Verdict.SUPERVISED.value, authorization_id=authorization_id, axes=axes
            )
            return {
                "verdict": Verdict.SUPERVISED.value,
                "reason": "authorization expired before revalidation",
                "execution_status": execution_status,
                "final_state": current_state.copy(),
                "evidence_log": str(log_path),
                "authorization_id": authorization_id,
                "decision": Verdict.SUPERVISED.value,
                "authorization": AuthorizationStatus.EXPIRED.value,
                "execution": ExecutionStatus.NOT_ATTEMPTED.value,
            }

        # Path 2: not GRANTED → NOT_ATTEMPTED
        if auth.status != AuthorizationStatus.GRANTED:
            execution_status = f"NOT_ATTEMPTED (authorization status={auth.status.value})"
            axes = {
                "decision": Verdict.SUPERVISED.value,
                "authorization": auth.status.value,
                "execution": ExecutionStatus.NOT_ATTEMPTED.value,
            }
            log_path = log_event(
                run_id, current_state, action, execution_status, current_state.copy(),
                Verdict.SUPERVISED.value, authorization_id=authorization_id, axes=axes
            )
            return {
                "verdict": Verdict.SUPERVISED.value,
                "reason": f"authorization not granted: {auth.status.value}",
                "execution_status": execution_status,
                "final_state": current_state.copy(),
                "evidence_log": str(log_path),
                "authorization_id": authorization_id,
                "decision": Verdict.SUPERVISED.value,
                "authorization": auth.status.value,
                "execution": ExecutionStatus.NOT_ATTEMPTED.value,
            }

        # Path 3: REVALIDATE against current reality
        revalidation = self.revalidation_gate.revalidate(
            auth, action, current_state, self.policy, self.agent_context
        )

        if not revalidation.passed:
            self.authorization_manager.invalidate(
                authorization_id, f"revalidation failed: {revalidation.failed_reason}")
            execution_status = f"CANCELLED_AFTER_REVALIDATION ({revalidation.failed_reason})"
            axes = {
                "decision": Verdict.SUPERVISED.value,
                "authorization": AuthorizationStatus.INVALIDATED.value,
                "execution": ExecutionStatus.CANCELLED_AFTER_REVALIDATION.value,
            }
            log_path = log_event(
                run_id, current_state, action, execution_status, current_state.copy(),
                Verdict.SUPERVISED.value, authorization_id=authorization_id, axes=axes
            )
            return {
                "verdict": Verdict.SUPERVISED.value,
                "reason": revalidation.failed_reason,
                "execution_status": execution_status,
                "final_state": current_state.copy(),
                "evidence_log": str(log_path),
                "authorization_id": authorization_id,
                "decision": Verdict.SUPERVISED.value,
                "authorization": AuthorizationStatus.INVALIDATED.value,
                "execution": ExecutionStatus.CANCELLED_AFTER_REVALIDATION.value,
                "revalidation_checks": [
                    {"name": c.name, "passed": c.passed, "reason": c.reason}
                    for c in revalidation.checks
                ],
            }

        # Path 4: revalidation passed → consume (one-shot, no re-check) → execute
        try:
            auth = self.authorization_manager.consume(
                authorization_id, action, current_state, validate=False)
        except PermissionError as e:
            execution_status = f"EXECUTED_FAILED (consume: {e})"
            axes = {
                "decision": Verdict.SUPERVISED.value,
                "authorization": auth.status.value,
                "execution": ExecutionStatus.EXECUTED_FAILED.value,
            }
            log_path = log_event(
                run_id, current_state, action, execution_status, current_state.copy(),
                Verdict.SUPERVISED.value, authorization_id=authorization_id, axes=axes
            )
            return {
                "verdict": Verdict.SUPERVISED.value,
                "reason": str(e),
                "execution_status": execution_status,
                "final_state": current_state.copy(),
                "evidence_log": str(log_path),
                "authorization_id": authorization_id,
                "decision": Verdict.SUPERVISED.value,
                "authorization": auth.status.value,
                "execution": ExecutionStatus.EXECUTED_FAILED.value,
            }

        execution_status = "EXECUTED_SUCCESS"
        new_state = {
            "t": current_state["t"] + 1,
            "replicas": action.get("to", current_state["replicas"]),
            "p95_ms": 176
        }
        axes = {
            "decision": Verdict.SUPERVISED.value,
            "authorization": AuthorizationStatus.CONSUMED.value,
            "execution": ExecutionStatus.EXECUTED_SUCCESS.value,
        }
        log_path = log_event(
            run_id, current_state, action, execution_status, new_state,
            Verdict.SUPERVISED.value, authorization_id=authorization_id, axes=axes
        )
        return {
            "verdict": Verdict.SUPERVISED.value,
            "reason": "revalidation passed; executed under granted bounded authorization",
            "execution_status": execution_status,
            "final_state": new_state,
            "evidence_log": str(log_path),
            "authorization_id": authorization_id,
            "decision": Verdict.SUPERVISED.value,
            "authorization": AuthorizationStatus.CONSUMED.value,
            "execution": ExecutionStatus.EXECUTED_SUCCESS.value,
        }
