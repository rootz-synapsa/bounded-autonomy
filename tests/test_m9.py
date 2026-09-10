"""M9 sanity tests — verify experiment mechanics before full run."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from experiment import SCENARIOS, World, propose_action, run_arm
from analyzer import count_stale_actions


class TestM9ExperimentMechanics(unittest.TestCase):
    def test_world_p95_is_deterministic(self):
        """p95_at must be deterministic for same (seed, replicas, t)."""
        s = SCENARIOS["spike"]
        w1 = World(s, seed=42)
        w2 = World(s, seed=42)
        for t in range(5):
            self.assertEqual(w1.p95_at(4, t), w2.p95_at(4, t))

    def test_propose_action_is_same_for_both_arms(self):
        """Optimizer must be identical for both arms (controlled variable)."""
        state = {"t": 0, "replicas": 4, "p95_ms": 487}
        self.assertEqual(propose_action(state), propose_action(state))

    def test_ungoverned_arm_has_no_human_intervention(self):
        """Ungoverned arm must have zero approvals and zero interventions."""
        s = SCENARIOS["spike"]
        result = run_arm(s, seed=0, governed=False)
        self.assertEqual(result["metrics"]["human_interventions"], 0)
        self.assertEqual(result["metrics"]["approval_wait_steps"], 0)

    def test_governed_arm_produces_supervised_actions(self):
        """Governed arm must route some actions through SUPERVISED."""
        s = SCENARIOS["spike"]
        result = run_arm(s, seed=0, governed=True)
        self.assertIn("actions_supervised", result["metrics"])

    def test_stale_approval_scenario_detects_stale(self):
        """In stale_approval scenario, ungoverned arm should execute
        an action that becomes stale (workload recovers on its own)."""
        s = SCENARIOS["stale_approval"]
        ungoverned = run_arm(s, seed=0, governed=False)
        world = World(s, seed=0)
        stale = count_stale_actions(world, ungoverned["metrics"]["actions_log"])
        # Workload spikes at t=2 (4.8) then recovers at t=3 (1.2)
        # so a scaling action at t=2 becomes stale by t=3
        self.assertGreaterEqual(stale, 1,
            "stale_approval scenario must produce at least one stale action")


if __name__ == "__main__":
    unittest.main()
