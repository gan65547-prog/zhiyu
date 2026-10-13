#!/usr/bin/env python3
"""Execute release-profile checks and write candidate-bound evidence."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manual-evidence", action="append", default=[], metavar="CAPABILITY_ID=PATH")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    output = Path(args.output)
    log_dir = output.parent / f"{output.stem}.logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    records = []
    for capability in profile["required_capabilities"]:
        command_records = []
        for command in capability["verification"]["commands"]:
            started = time.monotonic()
            result = subprocess.run(command, cwd=root, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            command_output = result.stdout.encode()
            log_path = log_dir / f"{capability['id']}-{len(command_records) + 1}.log"
            log_path.write_bytes(command_output)
            command_records.append({"command": command, "exit_code": result.returncode, "duration_seconds": round(time.monotonic() - started, 3), "log_path": str(log_path), "output_sha256": digest(command_output)})
        status = "PASS" if all(item["exit_code"] == 0 for item in command_records) else "FAIL"
        records.append({"id": capability["id"], "status": status, "commands": command_records})
    manual_evidence = []
    for item in args.manual_evidence:
        if "=" not in item:
            raise SystemExit("--manual-evidence must use CAPABILITY_ID=PATH")
        capability_id, raw_path = item.split("=", 1)
        path = Path(raw_path)
        if not path.is_file():
            raise SystemExit(f"manual evidence file not found: {path}")
        manual_evidence.append({"id": capability_id, "path": str(path), "sha256": digest(path.read_bytes())})
    manifest = {"release_id": profile["release_id"], "head_sha": head, "generated_at": datetime.now(timezone.utc).isoformat(), "overall": "PASS" if all(item["status"] == "PASS" for item in records) else "FAIL", "capabilities": records, "manual_evidence": manual_evidence}
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"evidence={output} overall={manifest['overall']} head={head}")
    return 0 if manifest["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
