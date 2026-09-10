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
        self.engine = BoundedExecutionEngine(self.policy)

    def test_m5_blocks_unsafe_action_and_preserves_state(self):
        # 1. Agent generates unsafe intent (scale to 8)
        initial_state = get_initial_state()
        action = propose_action(initial_state) # Returns scale to 8
        
        # 2. Process through Bounded Engine
        result = self.engine.process_intent("RUN-M5-001", initial_state, action)
        
        # 3. ASSERT: Enforcement worked
        self.assertEqual(result["verdict"], "DENIED")
        self.assertIn("BLOCKED", result["execution_status"])
        
        # 4. ASSERT: State was NOT changed (Fail-Closed)
        self.assertEqual(result["final_state"]["replicas"], initial_state["replicas"])
        self.assertEqual(result["final_state"]["p95_ms"], initial_state["p95_ms"])
        
        # 5. ASSERT: Evidence was logged
        self.assertTrue(Path(result["evidence_log"]).exists())
        with open(result["evidence_log"], "r") as f:
            logged_event = json.loads(f.readline())
            
        self.assertEqual(logged_event["verdict"], "DENIED")
        self.assertEqual(logged_event["action"]["to"], 8)
        
        print("\n" + "="*50)
        print("M5 ENFORCEMENT PROOF (AGENT FLIGHT RECORDER)")
        print("="*50)
        print(f"Agent Intent: {logged_event['action']['type']} to {logged_event['action']['to']} replicas")
        print(f"Gate Verdict: {logged_event['verdict']}")
        print(f"Execution   : {logged_event['execution_status']}")
        print(f"State Change: {initial_state['replicas']} -> {logged_event['final_state']['replicas']} replicas (UNCHANGED)")
        print(f"Evidence    : Saved to {logged_event['run_id']} log")
        print("="*50 + "\n")

    def test_m5_allows_safe_action_and_updates_state(self):
        # Test a safe action
        safe_action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 500}
        
        result = self.engine.process_intent("RUN-M5-002", initial_state, safe_action)
        
        self.assertEqual(result["verdict"], "AUTHORIZED")
        self.assertEqual(result["execution_status"], "EXECUTED_SUCCESS")
        self.assertEqual(result["final_state"]["replicas"], 4) # State changed!

if __name__ == "__main__":
    unittest.main()
