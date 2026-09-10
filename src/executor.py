def execute(action: dict) -> str:
    if action["type"] == "SCALE_REPLICAS":
        return "EXECUTED_SUCCESS"
    return "NOOP"
