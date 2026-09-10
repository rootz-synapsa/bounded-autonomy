import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator import get_initial_state
from optimizer import propose_action
from governance import DecisionEngine, Verdict

class TestH1GovernedFlow(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()
        self.policy = {"absolute_max_replicas": 10}
        self.agent_context = {
            "actor_id": "inference-autopilot",
            "authority": {
                "auto_scale_max": 6,
                "supervised_scale_max": 10
            }
        }
    
    def test_h1_policy_violation_results_in_block(self):
        """Policy violation (>10) → BLOCK (no human override)."""
        action = {"type": "SCALE_REPLICAS", "from": 8, "to": 12}
        initial_state = {"t": 0, "replicas": 8, "p95_ms": 400}
        
        verdict, reason = self.engine.evaluate(action, self.policy, self.agent_context, initial_state)
        
        self.assertEqual(verdict, Verdict.BLOCK)
        self.assertIn("Exceeds absolute policy ceiling", reason)
        
        print("\n" + "="*40)
        print("H1 POLICY VIOLATION → BLOCK")
        print("="*40)
        print(f"Intent: {action['type']} to {action['to']} replicas")
        print(f"Policy ceiling: {self.policy['absolute_max_replicas']}")
        print(f"Verdict: {verdict.value}")
        print(f"Reason: {reason}")
        print("="*40 + "\n")
    
    def test_h1_authority_insufficient_results_in_supervised(self):
        """Policy OK, within supervised envelope, exceeds auto envelope → SUPERVISED."""
        action = {"type": "SCALE_REPLICAS", "from": 4, "to": 8}  # 6 < 8 ≤ 10
        initial_state = {"t": 0, "replicas": 4, "p95_ms": 487}
        
        verdict, reason = self.engine.evaluate(action, self.policy, self.agent_context, initial_state)
        
        self.assertEqual(verdict, Verdict.SUPERVISED)
        self.assertIn("Exceeds autonomous envelope", reason)
        self.assertIn("requires supervision", reason)
        
        print("\n" + "="*40)
        print("H1 AUTHORITY INSUFFICIENT → SUPERVISED")
        print("="*40)
        print(f"Intent: {action['type']} to {action['to']} replicas")
        print(f"Auto envelope: ≤{self.agent_context['authority']['auto_scale_max']}")
        print(f"Supervised envelope: ≤{self.agent_context['authority']['supervised_scale_max']}")
        print(f"Verdict: {verdict.value}")
        print(f"Reason: {reason}")
        print("="*40 + "\n")
    
    def test_h1_within_autonomous_envelope_results_in_auto(self):
        """Policy OK, within auto envelope → AUTO."""
        action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}  # 4 ≤ 6
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 500}
        
        verdict, reason = self.engine.evaluate(action, self.policy, self.agent_context, initial_state)
        
        self.assertEqual(verdict, Verdict.AUTO)
        self.assertIn("All evaluations passed", reason)

if __name__ == "__main__":
    unittest.main()
