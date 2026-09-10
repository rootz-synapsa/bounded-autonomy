import json
from pathlib import Path

def log_event(run_id: str, initial: dict, action: dict, execution: str, final: dict):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    event = {
        "run_id": run_id,
        "initial_state": initial,
        "action": action,
        "execution": execution,
        "final_state": final
    }
    with open(data_dir / "events.jsonl", "a") as f:
        f.write(json.dumps(event) + "\n")
    return data_dir / "events.jsonl"
