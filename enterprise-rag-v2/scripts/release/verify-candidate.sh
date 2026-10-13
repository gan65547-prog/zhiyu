#!/usr/bin/env bash
# Verify a release candidate before creating or promoting an immutable release tag.
#
# This is intentionally strict. A liveness response or a mutable image tag is not
# release evidence. The caller must provide the pre-production evidence paths and
# the registry digests that will actually be deployed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PROFILE="${RELEASE_PROFILE:-}"
BASE_URL="${RELEASE_BASE_URL:-}"
BACKUP_EVIDENCE="${RELEASE_BACKUP_EVIDENCE:-}"
ROLLBACK_EVIDENCE="${RELEASE_ROLLBACK_EVIDENCE:-}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/release/verify-candidate.sh [--profile path] [--base-url URL]

Required environment for a production candidate:
  WEB_IMAGE, WORKER_IMAGE       registry/name@sha256:<64 hex chars>
  RELEASE_GIT_SHA                full SHA of the frozen commit
  RELEASE_BACKUP_EVIDENCE        readable backup/restore evidence file
  RELEASE_ROLLBACK_EVIDENCE      readable rollback evidence file
  DB_PASSWORD, JWT_SECRET, CSRF_SECRET
  INTERNAL_API_KEYS, INTERNAL_IP_WHITELIST
  DEEPSEEK_API_KEY or OPENAI_API_KEY
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

failures=0
fail() {
  echo "ERROR: $1" >&2
  failures=$((failures + 1))
}

require_env() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "$value" ]]; then
    fail "missing required environment variable: ${name}"
  fi
}

require_secret() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "$value" ]]; then
    fail "missing required secret: ${name}"
  elif [[ "$value" =~ ^(change[-_].*|your_.*|replace[-_].*|.*placeholder.*)$ ]]; then
    fail "placeholder value is not allowed for secret: ${name}"
  elif [[ ${#value} -lt 32 ]]; then
    fail "secret is shorter than 32 characters: ${name}"
  fi
}

require_digest_image() {
  local name="$1"
  local value="${!name:-}"
  if [[ ! "$value" =~ ^[^/@[:space:]]+/[^@[:space:]]+@sha256:[0-9a-fA-F]{64}$ ]]; then
    fail "${name} must be a registry image pinned by digest (registry/name@sha256:<64 hex chars>)"
  fi
}

if [[ -z "$PROFILE" ]]; then
  fail "release profile is required (set RELEASE_PROFILE to a protected candidate profile)"
elif [[ ! -r "$PROFILE" ]]; then
  fail "release profile is not readable: ${PROFILE}"
else
  if rg -n '\| (FAIL|BLOCKED|NOT RUN|UNKNOWN) \|' "$PROFILE" >/tmp/ganfy-release-profile-blockers.$$ 2>/dev/null; then
    while IFS= read -r line; do
      fail "release profile contains a hard blocker: ${line}"
    done < /tmp/ganfy-release-profile-blockers.$$
  fi
  rm -f /tmp/ganfy-release-profile-blockers.$$ 2>/dev/null || true

candidate_sha="$(sed -nE 's/^- 候选 commit[：:][[:space:]]*`([^`]+)`.*/\1/p' "$PROFILE" | head -n1)"
current_sha="$(git rev-parse --short=8 HEAD)"
candidate_full_sha=""
if [[ -z "$candidate_sha" ]]; then
  fail "release profile does not declare a candidate commit"
elif [[ "$candidate_sha" != "$current_sha" ]]; then
    candidate_full_sha="$(git rev-parse "${candidate_sha}^{commit}" 2>/dev/null || true)"
    candidate_commit="$candidate_full_sha"
    # A post-freeze correction to the repeatable live-regression harness is
    # evidence metadata, not a runtime artifact. Keep this allowlist exact:
    # application code, Dockerfiles, migrations and deployment files still
    # make the candidate fail closed.
    if [[ -z "$candidate_commit" ]] || git diff --name-only "$candidate_commit" HEAD | rg -v '(^|.*/)docs/release/|(^|.*/)scripts/release/verify-candidate\.sh$|(^|.*/)tests/manual/workbench_live_regression\.py$' | grep -q .; then
      fail "release profile candidate (${candidate_sha}) does not match HEAD (${current_sha})"
    else
      echo "Candidate code commit ${candidate_sha} is frozen; HEAD only updates its release profile."
    fi
else
  candidate_full_sha="$(git rev-parse "${candidate_sha}^{commit}" 2>/dev/null || true)"
fi
fi

require_env WEB_IMAGE
require_env WORKER_IMAGE
require_env RELEASE_GIT_SHA
require_digest_image WEB_IMAGE
require_digest_image WORKER_IMAGE

full_sha="$(git rev-parse HEAD)"
expected_release_sha="${candidate_full_sha:-$full_sha}"
if [[ "${RELEASE_GIT_SHA:-}" != "$expected_release_sha" ]]; then
  fail "RELEASE_GIT_SHA does not match the frozen candidate commit (${expected_release_sha})"
fi

require_secret DB_PASSWORD
require_secret JWT_SECRET
require_secret CSRF_SECRET
if [[ -z "${DEEPSEEK_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  fail "one of DEEPSEEK_API_KEY or OPENAI_API_KEY is required"
fi
require_env INTERNAL_API_KEYS
require_env INTERNAL_IP_WHITELIST

if [[ -z "$BACKUP_EVIDENCE" || ! -r "$BACKUP_EVIDENCE" ]]; then
  fail "backup/restore evidence file is missing or unreadable (RELEASE_BACKUP_EVIDENCE)"
fi
if [[ -z "$ROLLBACK_EVIDENCE" || ! -r "$ROLLBACK_EVIDENCE" ]]; then
  fail "rollback evidence file is missing or unreadable (RELEASE_ROLLBACK_EVIDENCE)"
fi

if [[ -n "$BASE_URL" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl is required for RELEASE_BASE_URL verification"
  else
    health_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 10 "${BASE_URL%/}/health" || true)"
    ready_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 10 "${BASE_URL%/}/health/ready" || true)"
    [[ "$health_code" == "200" ]] || fail "health endpoint returned HTTP ${health_code:-no-response}"
    [[ "$ready_code" == "200" ]] || fail "readiness endpoint returned HTTP ${ready_code:-no-response}"
  fi
fi

if (( failures > 0 )); then
  echo "Candidate verification failed with ${failures} blocker(s). No release tag is permitted." >&2
  exit 1
fi

echo "Candidate verification passed: ${full_sha}"
echo "Web image: ${WEB_IMAGE}"
echo "Worker image: ${WORKER_IMAGE}"
