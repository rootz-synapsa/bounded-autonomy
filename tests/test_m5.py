"""
M5 Enforcement Proof — Killer A/B Scenario
H0 (ungoverned): 4→8 EXECUTES
H1 (governed): 4→8 SUPERVISED (within supervised envelope, exceeds auto envelope)
"""
import unittest
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator import get_initial_state
from optimizer import propose_action
from engine import BoundedExecutionEngine

class TestM5Enforcement(unittest.TestCase):
    def setUp(self):
        self.event_log = Path("data/events.jsonl")
        if self.event_log.exists():
            self.event_log.unlink()
        self.policy = {"absolute_max_replicas": 10}
        self.agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {"auto_scale_max": 6, "supervised_scale_max": 10}
        }
        self.engine = BoundedExecutionEngine(self.policy, self.agent_context)

    def test_m5_killer_scenario_4_to_8_is_supervised(self):
        """KILLER A/B SCENARIO: H0 (4→8) executes; H1 (4→8) is SUPERVISED.
        
        4→8 exceeds auto envelope (6) but is within supervised envelope (10)
        and within policy ceiling (10). This is the bounded authorization case.
        """
        initial_state = get_initial_state()  # replicas=4
        action = propose_action(initial_state)  # scale to 8
        
        result = self.engine.process_intent("RUN-M5-KILLER", initial_state, action)
        
        # This is SUPERVISED, not BLOCK — because 8 is within supervised envelope
        self.assertEqual(result["verdict"], "SUPERVISED")
        self.assertIn("SUPERVISED", result["execution_status"])
        self.assertEqual(result["final_state"]["replicas"], initial_state["replicas"])  # Unchanged
        
        self.assertTrue(Path(result["evidence_log"]).exists())
        with open(result["evidence_log"], "r") as f:
            logged_event = json.loads(f.readline())
        
        self.assertEqual(logged_event["verdict"], "SUPERVISED")
        self.assertEqual(logged_event["action"]["to"], 8)
        
        print("\n" + "="*60)
        print("M5 KILLER A/B SCENARIO (Bounded Authority)")
        print("="*60)
        print(f"H0 (ungoverned): 4 → 8 → EXECUTES")
        print(f"H1 (governed)  : 4 → 8 → SUPERVISED (awaiting bounded approval)")
        print(f"Gate Verdict: {logged_event['verdict']}")
        print(f"State Change: UNCHANGED (state preserved)")
        print(f"Evidence    : {logged_event['run_id']} log")
        print("✓ Governance does not forbid autonomy — it defines its bounds")
        print("="*60 + "\n")

    def test_m5_allows_safe_action_and_updates_state(self):
        """Within auto envelope → AUTO → execute."""
        safe_action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}  # 4 ≤ 6
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 500}
        
        result = self.engine.process_intent("RUN-M5-002", initial_state, safe_action)
        
        self.assertEqual(result["verdict"], "AUTO")
        self.assertEqual(result["execution_status"], "EXECUTED_SUCCESS")
        self.assertEqual(result["final_state"]["replicas"], 4)

if __name__ == "__main__":
    unittest.main()
