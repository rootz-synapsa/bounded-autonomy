#!/usr/bin/env python3
import sys
sys.path.insert(0, "src")

from authorization import AuthorizationManager
from engine import BoundedExecutionEngine
from experiment import POLICY, AGENT, JUSTIFICATION

def scene_auto():
    print("SCENE 1: AUTO")
    print("-" * 50)
    manager = AuthorizationManager(clock=lambda: 0, default_ttl_seconds=300)
    engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=manager)
    action = {"type": "SCALE_REPLICAS", "from": 2, "to": 4, "reason": "high_latency"}
    state = {"t": 0, "replicas": 2, "p95_ms": 450}
    print(f"Agent proposes: SCALE_REPLICAS 2 -> 4")
    result = engine.process_intent("DEMO-AUTO", state, action)
    print(f"Decision: {result['decision']} (within auto_scale_max=6)")
    print(f"Execution: {result['execution']}")
    print(f"State: replicas 2 -> {result['final_state']['replicas']}")
    print()
    print("No human needed. Bounded autonomy means authority within envelope.")

def scene_supervised():
    print("SCENE 2: SUPERVISED")
    print("-" * 50)
    manager = AuthorizationManager(clock=lambda: 0, default_ttl_seconds=300)
    engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=manager)
    action = {"type": "SCALE_REPLICAS", "from": 4, "to": 8, "reason": "high_latency"}
    state = {"t": 0, "replicas": 4, "p95_ms": 450}
    print(f"Agent proposes: SCALE_REPLICAS 4 -> 8")
    result = engine.process_intent("DEMO-SUPERVISED", state, action)
    print(f"Decision: {result['decision']} (exceeds auto=6, within supervised=10)")
    if result["authorization_id"]:
        auth_id = result["authorization_id"]
        print("Authorization: PENDING")
        manager.grant(auth_id, "human-ops-1", state, context_predicate=JUSTIFICATION)
        print("Authorization: PENDING -> GRANTED by human-ops-1")
        exec_result = engine.execute_with_revalidation("DEMO-EXEC", state, action, auth_id)
        print(f"Execution: {exec_result['execution']}")
        print(f"State: replicas 4 -> {exec_result['final_state']['replicas']}")
    print()
    print("Governance defines bounds, not forbids autonomy.")

def scene_stale():
    print("SCENE 3: STALE APPROVAL")
    print("-" * 50)
    clock = [0]
    manager = AuthorizationManager(clock=lambda: clock[0], default_ttl_seconds=300)
    engine = BoundedExecutionEngine(POLICY, AGENT, authorization_manager=manager)
    action = {"type": "SCALE_REPLICAS", "from": 6, "to": 7, "reason": "high_latency"}
    state_t0 = {"t": 0, "replicas": 6, "p95_ms": 487}
    print(f"T0: p95=487ms, propose SCALE_REPLICAS 6 -> 7")
    result = engine.process_intent("DEMO-STALE", state_t0, action)
    print(f"    Decision: {result['decision']}")
    if result["authorization_id"]:
        auth_id = result["authorization_id"]
        print("    Authorization: PENDING")
        manager.grant(auth_id, "human-ops-1", state_t0, context_predicate=JUSTIFICATION)
        print("    Authorization: PENDING -> GRANTED by human-ops-1")
        print()
        state_t1 = {"t": 1, "replicas": 6, "p95_ms": 165}
        print("T1: Workload changes, p95=165ms")
        print()
        print("T2: Revalidation Gate:")
        clock[0] = 1
        exec_result = engine.execute_with_revalidation("DEMO-STALE-EXEC", state_t1, action, auth_id)
        if "revalidation_checks" in exec_result:
            for check in exec_result["revalidation_checks"]:
                status = "PASS" if check["passed"] else "FAIL"
                print(f"    - {check['name']}: {status}")
        print(f"    Authorization: GRANTED -> {exec_result['authorization']}")
        print(f"    Execution: {exec_result['execution']}")
        print()
        print("The action was approved. It was no longer justified. So it never executed.")

scene = sys.argv[2] if len(sys.argv) > 2 else "all"
if scene == "auto": scene_auto()
elif scene == "supervised": scene_supervised()
elif scene == "stale": scene_stale()
elif scene == "all":
    scene_auto(); print(); scene_supervised(); print(); scene_stale()
