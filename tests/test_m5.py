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
        self.policy = {"max_replicas": 6}
        self.agent_context = {"role": "admin"}
        self.engine = BoundedExecutionEngine(self.policy, self.agent_context)

    def test_m5_blocks_unsafe_action_and_preserves_state(self):
        initial_state = get_initial_state()
        action = propose_action(initial_state)  # Scale to 8
        
        result = self.engine.process_intent("RUN-M5-001", initial_state, action)
        
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("BLOCKED", result["execution_status"])
        self.assertEqual(result["final_state"]["replicas"], initial_state["replicas"])
        
        self.assertTrue(Path(result["evidence_log"]).exists())
        with open(result["evidence_log"], "r") as f:
            logged_event = json.loads(f.readline())
        
        self.assertEqual(logged_event["verdict"], "BLOCK")
        
        print("\n" + "="*50)
        print("M5 ENFORCEMENT PROOF (Bounded Autonomy)")
        print("="*50)
        print(f"Agent Intent: {logged_event['action']['type']} to {logged_event['action']['to']} replicas")
        print(f"Gate Verdict: {logged_event['verdict']}")
        print(f"Execution   : {logged_event['execution']}")
        print(f"State Change: UNCHANGED")
        print(f"Evidence    : {logged_event['run_id']} log")
        print("="*50 + "\n")

    def test_m5_allows_safe_action_and_updates_state(self):
        safe_action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 500}
        
        result = self.engine.process_intent("RUN-M5-002", initial_state, safe_action)
        
        self.assertEqual(result["verdict"], "AUTO")
        self.assertEqual(result["execution_status"], "EXECUTED_SUCCESS")
        self.assertEqual(result["final_state"]["replicas"], 4)

if __name__ == "__main__":
    unittest.main()
