"""
M7 Authorization Lifecycle: PENDING → GRANTED → CONSUMED, with
EXPIRED / INVALIDATED fail-closed paths.
"""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from authorization import AuthorizationManager, AuthorizationStatus
from engine import BoundedExecutionEngine


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


class TestM7AuthorizationLifecycle(unittest.TestCase):
    def setUp(self):
        self.event_log = Path("data/events.jsonl")
        if self.event_log.exists():
            self.event_log.unlink()
        self.clock = FakeClock()
        self.manager = AuthorizationManager(clock=self.clock, default_ttl_seconds=300.0)
        self.engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=self.manager)
        self.state = {"t": 0, "replicas": 4, "p95_ms": 487}
        self.action = {"type": "SCALE_REPLICAS", "from": 4, "to": 8}

    def test_m7_supervised_creates_pending_authorization(self):
        result = self.engine.process_intent("RUN-M7-001", self.state, self.action)
        self.assertEqual(result["verdict"], "SUPERVISED")
        self.assertIsNotNone(result["authorization_id"])
        auth = self.manager.get(result["authorization_id"])
        self.assertEqual(auth.status, AuthorizationStatus.PENDING)
        self.assertEqual(result["final_state"], self.state)

    def test_m7_grant_then_consume_executes_once(self):
        result = self.engine.process_intent("RUN-M7-002", self.state, self.action)
        auth_id = result["authorization_id"]
        self.manager.grant(auth_id, "human-ops-1", self.state)

        exec_result = self.engine.execute_authorized("RUN-M7-002-EXEC", self.state, self.action, auth_id)
        self.assertEqual(exec_result["execution_status"], "EXECUTED_UNDER_AUTHORIZATION")
        self.assertEqual(exec_result["authorization_status"], "CONSUMED")
        self.assertEqual(exec_result["final_state"]["replicas"], 8)

        # Replay must fail closed
        replay = self.engine.execute_authorized("RUN-M7-002-REPLAY", self.state, self.action, auth_id)
        self.assertTrue(replay["execution_status"].startswith("BLOCKED"))
        self.assertEqual(replay["authorization_status"], "CONSUMED")
        self.assertEqual(replay["final_state"], self.state)

        print("\n" + "="*60)
        print("M7 AUTHORIZATION LIFECYCLE (one-shot bounded approval)")
        print("="*60)
        print("PENDING  → grant(human-ops-1) → GRANTED")
        print("GRANTED  → consume(exact action, exact state) → CONSUMED → EXECUTED")
        print("REPLAY   → BLOCKED (authorization already consumed)")
        print("="*60 + "\n")

    def test_m7_expired_pending_cannot_be_granted(self):
        result = self.engine.process_intent("RUN-M7-003", self.state, self.action)
        auth_id = result["authorization_id"]
        self.clock.advance(301)
        with self.assertRaises(ValueError):
            self.manager.grant(auth_id, "human-ops-1", self.state)
        self.assertEqual(self.manager.get(auth_id).status, AuthorizationStatus.EXPIRED)

    def test_m7_granted_authorization_expires_before_use(self):
        result = self.engine.process_intent("RUN-M7-004", self.state, self.action)
        auth_id = result["authorization_id"]
        self.manager.grant(auth_id, "human-ops-1", self.state)
        self.clock.advance(301)
        exec_result = self.engine.execute_authorized("RUN-M7-004-EXEC", self.state, self.action, auth_id)
        self.assertTrue(exec_result["execution_status"].startswith("BLOCKED"))
        self.assertEqual(exec_result["authorization_status"], "EXPIRED")
        self.assertEqual(exec_result["final_state"], self.state)

    def test_m7_state_change_invalidates_granted_authorization(self):
        result = self.engine.process_intent("RUN-M7-005", self.state, self.action)
        auth_id = result["authorization_id"]
        self.manager.grant(auth_id, "human-ops-1", self.state)
        drifted_state = {"t": 1, "replicas": 5, "p95_ms": 400}
        exec_result = self.engine.execute_authorized("RUN-M7-005-EXEC", drifted_state, self.action, auth_id)
        self.assertTrue(exec_result["execution_status"].startswith("BLOCKED"))
        self.assertEqual(exec_result["authorization_status"], "INVALIDATED")
        self.assertIn("state changed since grant", exec_result["reason"])

    def test_m7_denied_authorization_cannot_be_consumed(self):
        result = self.engine.process_intent("RUN-M7-006", self.state, self.action)
        auth_id = result["authorization_id"]
        self.manager.deny(auth_id, "human-ops-1", "change freeze in effect")
        self.assertEqual(self.manager.get(auth_id).status, AuthorizationStatus.INVALIDATED)
        exec_result = self.engine.execute_authorized("RUN-M7-006-EXEC", self.state, self.action, auth_id)
        self.assertTrue(exec_result["execution_status"].startswith("BLOCKED"))
        self.assertEqual(exec_result["final_state"], self.state)


if __name__ == "__main__":
    unittest.main()
