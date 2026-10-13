#!/usr/bin/env python3
"""Validate the portable, project-specific release profile."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] invalid release profile: {exc}")
        return 1

    errors: list[str] = []
    for key in ("profile_version", "release_id", "status", "owner", "scope", "required_capabilities", "exclusions", "release_rules"):
        if not data.get(key):
            errors.append(f"missing top-level key: {key}")
    if data.get("status") not in {"draft", "rc", "verified", "approved", "tagged", "released", "blocked", "rollback"}:
        errors.append("status is not a supported release state")

    seen: set[str] = set()
    capabilities = data.get("required_capabilities", [])
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("required_capabilities must be a non-empty array")
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"capability[{index}] must be an object")
            continue
        for key in ("id", "name", "test_id", "evidence", "risk", "owner"):
            if not isinstance(capability.get(key), str) or not capability[key].strip():
                errors.append(f"capability[{index}] missing {key}")
        identifier = capability.get("id")
        if identifier in seen:
            errors.append(f"duplicate capability id: {identifier}")
        seen.add(identifier)
        if not isinstance(capability.get("acceptance_criteria"), list) or not capability["acceptance_criteria"]:
            errors.append(f"capability[{index}] requires acceptance_criteria")
        verification = capability.get("verification")
        if not isinstance(verification, dict) or verification.get("mode") not in {"automated", "manual", "hybrid"}:
            errors.append(f"capability[{index}] requires a valid verification mode")
        elif not isinstance(verification.get("commands"), list) or not verification["commands"]:
            errors.append(f"capability[{index}] requires one or more verification commands")

    for key in ("all_required_pass", "unknown_blocks_release", "current_candidate_evidence_required", "tag_requires_verified_commit"):
        if data.get("release_rules", {}).get(key) is not True:
            errors.append(f"release_rules.{key} must be true")
    if errors:
        print("===== RELEASE PROFILE: FAILED =====")
        print("\n".join(f"[FAIL] {error}" for error in errors))
        return 1
    print(f"===== RELEASE PROFILE: PASS ({data['release_id']}, {len(capabilities)} required capabilities) =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
