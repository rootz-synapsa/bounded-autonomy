import unittest
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator import get_initial_state, get_post_action_state
from optimizer import propose_action
from executor import execute
from logger import log_event

class TestH0Baseline(unittest.TestCase):
    def setUp(self):
        self.event_log = Path("data/events.jsonl")
        if self.event_log.exists():
            self.event_log.unlink()

    def test_h0_ungoverned_flow(self):
        # 1. Telemetry Snapshot
        initial_state = get_initial_state()
        
        # 2. Optimizer Decision (Ungoverned)
        action = propose_action(initial_state)
        
        # 3. Direct Execute
        execution_status = execute(action)
        
        # 4. Outcome
        final_state = get_post_action_state(action["to"])
        
        # 5. Raw Event Log
        log_path = log_event("RUN-001", initial_state, action, execution_status, final_state)
        
        # Assertions
        self.assertTrue(log_path.exists())
        with open(log_path, "r") as f:
            logged_event = json.loads(f.readline())
            
        self.assertEqual(logged_event["execution"], "EXECUTED_SUCCESS")
        self.assertEqual(logged_event["final_state"]["replicas"], 8)
        self.assertEqual(logged_event["final_state"]["p95_ms"], 176)
        
        # Print formatted output for verification
        print("\n" + "="*40)
        print("H0 BASELINE OUTPUT")
        print("="*40)
        print(f"t={logged_event['initial_state']['t']}")
        print(f"replicas={logged_event['initial_state']['replicas']}")
        print(f"p95={logged_event['initial_state']['p95_ms']}ms")
        print(f"\noptimizer:\n{action['type']} {action['from']} → {action['to']}")
        print(f"\nexecution:\n{logged_event['execution']}")
        print(f"\nafter:")
        print(f"replicas={logged_event['final_state']['replicas']}")
        print(f"p95={logged_event['final_state']['p95_ms']}ms")
        print(f"\nevent written:\n{log_path}")
        print("="*40 + "\n")

if __name__ == "__main__":
    unittest.main()
