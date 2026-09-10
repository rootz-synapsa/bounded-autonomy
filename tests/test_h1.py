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
        self.policy = {"max_replicas": 6}
    
    def test_h1_policy_fail_results_in_block(self):
        """Policy violation → BLOCK (not SUPERVISED)."""
        initial_state = get_initial_state()
        action = propose_action(initial_state)  # Scale to 8
        self.assertEqual(action["to"], 8)
        
        agent_context = {"role": "admin"}
        verdict, reason = self.engine.evaluate(action, self.policy, agent_context, initial_state)
        
        self.assertEqual(verdict, Verdict.BLOCK)
        self.assertIn("Exceeds max replicas", reason)
        
        print("\n" + "="*40)
        print("H1 POLICY VIOLATION → BLOCK")
        print("="*40)
        print(f"Intent: {action['type']} to {action['to']} replicas")
        print(f"Verdict: {verdict.value}")
        print(f"Reason: {reason}")
        print("="*40 + "\n")
    
    def test_h1_authority_insufficient_results_in_supervised(self):
        """Policy OK, authority insufficient → SUPERVISED."""
        action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}
        agent_context = {"role": "observer"}  # Not admin
        initial_state = {"t": 0, "replicas": 2, "p95_ms": 300}
        
        verdict, reason = self.engine.evaluate(action, self.policy, agent_context, initial_state)
        
        self.assertEqual(verdict, Verdict.SUPERVISED)
        self.assertIn("requires admin role", reason)

if __name__ == "__main__":
    unittest.main()
