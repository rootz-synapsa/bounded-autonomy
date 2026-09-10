def propose_action(current_state: dict) -> dict:
    if current_state["p95_ms"] > 400:
        return {
            "type": "SCALE_REPLICAS",
            "from": current_state["replicas"],
            "to": current_state["replicas"] * 2,
            "reason": "high_latency"
        }
    return {"type": "NOOP"}
