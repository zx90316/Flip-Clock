"""Copy one authentic recorded state for a labelled diagnostic continuation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def main(run, requested_time, output):
    run = Path(run).resolve(); output = Path(output).resolve()
    config = json.loads((run / "run_config.json").read_text())
    states = np.load(run / "states.npz", allow_pickle=False)
    index = int(np.argmin(abs(states["time_s"] - requested_time)))
    if hashlib.sha256((run / "model/model.xml").read_bytes()).hexdigest() != config["model_sha256"]:
        raise ValueError("Source model hash mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, qpos=states["qpos"][index], qvel=states["qvel"][index], model_sha256=config["model_sha256"],
                        source_run=run.name, source_time_s=states["time_s"][index], source_states_sha256=hashlib.sha256((run / "states.npz").read_bytes()).hexdigest())
    print(json.dumps({"output": str(output), "run": run.name, "sample_time_s": float(states["time_s"][index]), "stage": str(states["stage"][index]), "state_interpolation": False}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("run"); parser.add_argument("--time", type=float, required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); main(args.run, args.time, args.out)
