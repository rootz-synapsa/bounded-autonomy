"""
M8 Revalidation Execution Gate — 6 acceptance tests + 1 killer scenario.
Authority is valid only while reality remains valid.
"""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from authorization import AuthorizationManager, AuthorizationStatus
from engine import BoundedExecutionEngine, ExecutionStatus


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start
    def __call__(self):
        return self.now
    def advance(self, seconds):
        self.now += seconds


POLICY = {"absolute_max_replicas": 10}
AGENT = {
    "actor_id": "inference-autopilot",
    "authority": {"auto_scale_max": 6, "supervised_scale_max": 10},
}
ACTION = {"type": "SCALE_REPLICAS", "from": 6, "to": 7}
JUSTIFICATION = {"metric": "p95_ms", "operator": ">", "threshold": 200}


class TestM8RevalidationGate(unittest.TestCase):
    def setUp(self):
        self.event_log = Path("data/events.jsonl")
        if self.event_log.exists():
            self.event_log.unlink()
        self.clock = FakeClock()
        self.manager = AuthorizationManager(clock=self.clock, default_ttl_seconds=300.0)
        self.engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=self.manager)
        self.state_t0 = {"t": 0, "replicas": 6, "p95_ms": 487}

    def _grant(self, run_id="RUN-M8"):
        result = self.engine.process_intent(run_id, self.state_t0, ACTION)
        self.assertEqual(result["decision"], "SUPERVISED")
        auth_id = result["authorization_id"]
        self.manager.grant(auth_id, "human-ops-1", self.state_t0,
                           context_predicate=JUSTIFICATION)
        return auth_id

    # --- Acceptance 1: GRANTED + same action + same valid context → execute
    def test_m8_revalidation_pass_executes(self):
        auth_id = self._grant()
        result = self.engine.execute_with_revalidation(
            "RUN-M8-001", self.state_t0, ACTION, auth_id)
        self.assertEqual(result["decision"], "SUPERVISED")
        self.assertEqual(result["authorization"], "CONSUMED")
        self.assertEqual(result["execution"], "EXECUTED_SUCCESS")
        self.assertEqual(result["final_state"]["replicas"], 7)

    # --- Acceptance 2: GRANTED + changed action → CANCELLED_AFTER_REVALIDATION
    def test_m8_changed_action_invalidated(self):
        auth_id = self._grant()
        different_action = {"type": "SCALE_REPLICAS", "from": 6, "to": 9}
        result = self.engine.execute_with_revalidation(
            "RUN-M8-002", self.state_t0, different_action, auth_id)
        self.assertEqual(result["authorization"], "INVALIDATED")
        self.assertEqual(result["execution"], "CANCELLED_AFTER_REVALIDATION")
        self.assertEqual(result["final_state"], self.state_t0)

    # --- Acceptance 3: GRANTED + context predicate false → cancel
    def test_m8_context_predicate_false_invalidated(self):
        auth_id = self._grant()
        drifted_state = {"t": 1, "replicas": 6, "p95_ms": 150}  # predicate 150 > 200 = FALSE
        result = self.engine.execute_with_revalidation(
            "RUN-M8-003", drifted_state, ACTION, auth_id)
        self.assertEqual(result["authorization"], "INVALIDATED")
        self.assertEqual(result["execution"], "CANCELLED_AFTER_REVALIDATION")

    # --- Acceptance 4: GRANTED + invariant now violated → no execution
    def test_m8_invariant_now_violated(self):
        auth_id = self._grant()
        frozen_state = {"t": 1, "replicas": 6, "p95_ms": 487, "maintenance_freeze": True}
        result = self.engine.execute_with_revalidation(
            "RUN-M8-004", frozen_state, ACTION, auth_id)
        self.assertEqual(result["authorization"], "INVALIDATED")
        self.assertEqual(result["execution"], "CANCELLED_AFTER_REVALIDATION")
        self.assertIn("maintenance freeze", result["reason"])

    # --- Acceptance 5: GRANTED + TTL expired before revalidation → EXPIRED
    def test_m8_ttl_expired_before_revalidation(self):
        auth_id = self._grant()
        self.clock.advance(301)
        result = self.engine.execute_with_revalidation(
            "RUN-M8-005", self.state_t0, ACTION, auth_id)
        self.assertEqual(result["authorization"], "EXPIRED")
        self.assertEqual(result["execution"], "NOT_ATTEMPTED")
        self.assertEqual(result["final_state"], self.state_t0)

    # --- Acceptance 6: GRANTED + policy changed since approval → invalidated
    def test_m8_policy_changed_since_approval(self):
        auth_id = self._grant()
        tightened_policy = {"absolute_max_replicas": 6}
        self.engine.policy = tightened_policy
        result = self.engine.execute_with_revalidation(
            "RUN-M8-006", self.state_t0, ACTION, auth_id)
        self.assertEqual(result["authorization"], "INVALIDATED")
        self.assertEqual(result["execution"], "CANCELLED_AFTER_REVALIDATION")
        self.assertIn("Exceeds absolute policy ceiling", result["reason"])

    # --- KILLER SCENARIO: the action was approved, but no longer justified
    def test_m8_killer_stale_approval(self):
        """
        T0  p95 = 487 ms; candidate = scale 6 → 7; decision = SUPERVISED
        T1  human approves; authorization = GRANTED
        T2  workload changes; p95 = 165 ms
        T3  revalidate justification: p95 > 200 ? FALSE
            → INVALIDATED → CANCELLED_AFTER_REVALIDATION
        """
        auth_id = self._grant("RUN-M8-KILLER")

        # T2: world moved on — latency recovered on its own
        state_t2 = {"t": 2, "replicas": 6, "p95_ms": 165}

        result = self.engine.execute_with_revalidation(
            "RUN-M8-KILLER-EXEC", state_t2, ACTION, auth_id)

        self.assertEqual(result["decision"], "SUPERVISED")
        self.assertEqual(result["authorization"], "INVALIDATED")
        self.assertEqual(result["execution"], "CANCELLED_AFTER_REVALIDATION")
        self.assertEqual(result["final_state"], state_t2)  # state preserved

        print("\n" + "="*64)
        print("M8 KILLER SCENARIO — STALE APPROVAL")
        print("="*64)
        print("T0  p95=487ms   candidate: scale 6→7   decision=SUPERVISED")
        print("T1  human approves                     authorization=GRANTED")
        print("T2  workload changes                   p95=165ms")
        print("T3  revalidate justification: p95 > 200 ?  FALSE")
        print("    authorization=INVALIDATED")
        print("    execution=CANCELLED_AFTER_REVALIDATION")
        print("-"*64)
        print("HERO EVIDENCE:")
        print('  "The action was approved. It was no longer justified.')
        print('   So it never executed."')
        print("="*64 + "\n")


if __name__ == "__main__":
    unittest.main()
