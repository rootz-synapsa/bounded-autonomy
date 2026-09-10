import unittest
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator import get_initial_state
from engine import BoundedExecutionEngine

class TestM6DecisionTaxonomy(unittest.TestCase):
    def setUp(self):
        self.event_log = Path("data/events.jsonl")
        if self.event_log.exists():
            self.event_log.unlink()
    
    def test_m6_auto_verdict_executes(self):
        """All checks pass → AUTO → execute."""
        policy = {"absolute_max_replicas": 10}
        agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {"auto_scale_max": 6, "supervised_scale_max": 10}
        }
        engine = BoundedExecutionEngine(policy, agent_context)
        
        action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}  # 4 ≤ 6
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 500}
        
        result = engine.process_intent("RUN-M6-AUTO", initial_state, action)
        
        self.assertEqual(result["verdict"], "AUTO")
        self.assertEqual(result["execution_status"], "EXECUTED_SUCCESS")
        self.assertEqual(result["final_state"]["replicas"], 4)
        
        print("\n" + "="*50)
        print("M6: AUTO verdict → automatic execution")
        print("="*50)
        print(f"Verdict: {result['verdict']}")
        print(f"Execution: {result['execution_status']}")
        print(f"State: {initial_state['replicas']} → {result['final_state']['replicas']}")
        print("="*50 + "\n")
    
    def test_m6_supervised_verdict_blocks_until_approval(self):
        """Policy OK, exceeds auto envelope, within supervised envelope → SUPERVISED."""
        policy = {"absolute_max_replicas": 10}
        agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {"auto_scale_max": 6, "supervised_scale_max": 10}
        }
        engine = BoundedExecutionEngine(policy, agent_context)
        
        action = {"type": "SCALE_REPLICAS", "from": 4, "to": 8}  # 6 < 8 ≤ 10
        initial_state = {"t": 0, "replicas": 4, "p95_ms": 487}
        
        result = engine.process_intent("RUN-M6-SUPERVISED", initial_state, action)
        
        self.assertEqual(result["verdict"], "SUPERVISED")
        self.assertIn("SUPERVISED", result["execution_status"])
        self.assertEqual(result["final_state"]["replicas"], initial_state["replicas"])
        
        print("\n" + "="*50)
        print("M6: SUPERVISED verdict → bounded authorization required")
        print("="*50)
        print(f"Verdict: {result['verdict']}")
        print(f"Status: {result['execution_status']}")
        print(f"State: UNCHANGED (awaiting approval)")
        print("="*50 + "\n")
    
    def test_m6_block_verdict_on_invariant_violation(self):
        """Invariant violation → BLOCK → fail-closed."""
        policy = {"absolute_max_replicas": 10}
        agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {"auto_scale_max": 6, "supervised_scale_max": 10}
        }
        engine = BoundedExecutionEngine(policy, agent_context)
        
        action = {"type": "DROP_DATABASE", "target": "production"}
        initial_state = {"t": 0, "replicas": 4, "p95_ms": 200}
        
        result = engine.process_intent("RUN-M6-BLOCK", initial_state, action)
        
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("BLOCKED", result["execution_status"])
        self.assertIn("forbidden", result["reason"])
        self.assertEqual(result["final_state"]["replicas"], initial_state["replicas"])
    
    def test_m6_block_verdict_on_policy_violation(self):
        """Policy violation (>absolute_max) → BLOCK (no human override)."""
        policy = {"absolute_max_replicas": 10}
        agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {"auto_scale_max": 6, "supervised_scale_max": 10}
        }
        engine = BoundedExecutionEngine(policy, agent_context)
        
        action = {"type": "SCALE_REPLICAS", "from": 8, "to": 12}  # 12 > 10
        initial_state = {"t": 0, "replicas": 8, "p95_ms": 300}
        
        result = engine.process_intent("RUN-M6-BLOCK-POLICY", initial_state, action)
        
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("Exceeds absolute policy ceiling", result["reason"])

if __name__ == "__main__":
    unittest.main()
