def get_initial_state():
    return {"t": 0, "replicas": 4, "p95_ms": 487}

def get_post_action_state(replicas: int):
    # Simulate improvement after scaling
    return {"t": 1, "replicas": replicas, "p95_ms": 176}
