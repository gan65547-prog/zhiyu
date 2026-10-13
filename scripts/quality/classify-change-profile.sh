#!/usr/bin/env bash
# Classify a Ganfy change; profiles can escalate but never be downgraded.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
BASE_REF="${CHANGE_BASE_REF:-}"

if [[ -n "$BASE_REF" ]] && git rev-parse --verify "${BASE_REF}^{commit}" >/dev/null 2>&1; then
  files="$(git diff --name-only "$BASE_REF"...HEAD)"
  churn="$(git diff --numstat "$BASE_REF"...HEAD | awk '{a+=$1+$2} END {print a+0}')"
else
  files="$( { git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard; } | sort -u)"
  churn="$( { git diff --numstat; git diff --cached --numstat; } | awk '{a+=$1+$2} END {print a+0}')"
fi

profile="fast"
reason="documents-only"
code_files=0
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  case "$file" in
    documents/*|*.md) ;;
    *) profile="standard"; reason="code-or-config:$file" ;;
  esac
  case "$file" in *.py|*.js|*.ts|*.vue) ((code_files+=1)) || true ;; esac
  case "$file" in
    enterprise-rag-v2/api/*|enterprise-rag-v2/services/*|enterprise-rag-v2/alembic/*|enterprise-rag-v2/core/config.py|enterprise-rag-v2/scripts/deploy/*|ops-center/app/*|.github/*|scripts/quality/*|release/*)
      profile="critical"; reason="security-data-release-path:$file" ;;
  esac
done <<< "$files"

if (( churn > 200 )); then profile="critical"; reason="diff-churn:$churn"; fi
if (( code_files > 5 )); then profile="critical"; reason="code-files:$code_files"; fi
printf 'profile=%s\nreason=%s\n' "$profile" "$reason"
