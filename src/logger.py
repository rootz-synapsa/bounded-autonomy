import json
from pathlib import Path
from datetime import datetime, timezone

def log_event(run_id: str, initial: dict, action: dict, execution: str, final: dict, verdict: str = "UNGOVERNED"):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "initial_state": initial,
        "action": action,
        "verdict": verdict,
        "execution_status": execution,
        "final_state": final
    }
    log_path = data_dir / "events.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")
    return log_path
