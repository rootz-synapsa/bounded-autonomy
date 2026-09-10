import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator import get_initial_state
from optimizer import propose_action
from governance import evaluate_action, Verdict

class TestH1GovernedFlow(unittest.TestCase):
    def test_h1_governance_intercepts_unsafe_action(self):
        # 1. Telemetry Snapshot
        initial_state = get_initial_state()
        
        # 2. Optimizer Decision (Ungoverned Intent)
        # H0 optimizer proposes scaling to 8 replicas
        action = propose_action(initial_state)
        self.assertEqual(action["to"], 8)
        
        # 3. INTERCEPT: Governance Gate Evaluation
        # Policy: Max 6 replicas allowed
        policy = {"max_replicas": 6}
        verdict, reason = evaluate_action(action, policy)
        
        # 4. ASSERT: Boundary works (Fail-Closed)
        self.assertEqual(verdict, Verdict.DENIED)
        self.assertIn("Exceeds maximum", reason)
        
        print("\n" + "="*40)
        print("H1 GOVERNANCE INTERCEPTION")
        print("="*40)
        print(f"Intent: {action['type']} to {action['to']} replicas")
        print(f"Policy: max_replicas = {policy['max_replicas']}")
        print(f"Verdict: {verdict.value}")
        print(f"Reason: {reason}")
        print("="*40 + "\n")

    def test_h1_governance_authorizes_safe_action(self):
        # Test a safe action
        safe_action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4}
        policy = {"max_replicas": 6}
        
        verdict, reason = evaluate_action(safe_action, policy)
        
        self.assertEqual(verdict, Verdict.AUTHORIZED)
        self.assertEqual(reason, "Within policy bounds")

if __name__ == "__main__":
    unittest.main()
