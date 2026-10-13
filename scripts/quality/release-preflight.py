#!/usr/bin/env python3
"""Hard-block release tags without verified current-candidate evidence."""
import argparse
import json
import hashlib
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    errors = []
    if profile.get("status") not in {"verified", "approved"}:
        errors.append("release profile status must be verified or approved")
    if evidence.get("release_id") != profile.get("release_id"):
        errors.append("evidence release_id does not match profile")
    if evidence.get("head_sha") != head:
        errors.append("evidence is not bound to current HEAD")
    if evidence.get("overall") != "PASS":
        errors.append("required automated evidence is not PASS")
    required = {item["id"] for item in profile.get("required_capabilities", [])}
    passed = {item.get("id") for item in evidence.get("capabilities", []) if item.get("status") == "PASS"}
    if required != passed:
        errors.append("not every required capability has PASS evidence")
    manual_required = {item["id"] for item in profile.get("required_capabilities", []) if item.get("verification", {}).get("mode") != "automated"}
    manual_supplied = {item.get("id") for item in evidence.get("manual_evidence", []) if item.get("path") and item.get("sha256")}
    if not manual_required.issubset(manual_supplied):
        errors.append("manual/hybrid evidence must be attached to the release record before tag")
    for item in evidence.get("manual_evidence", []):
        path = Path(item.get("path", ""))
        if not path.is_file():
            errors.append(f"manual evidence file not found: {path}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != item.get("sha256"):
            errors.append(f"manual evidence hash mismatch: {path}")
    if errors:
        print("===== RELEASE PREFLIGHT: BLOCKED =====")
        print("\n".join(f"[BLOCKED] {error}" for error in errors))
        return 1
    print("===== RELEASE PREFLIGHT: VERIFIED =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
