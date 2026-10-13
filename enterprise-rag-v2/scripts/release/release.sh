#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

VERSION=""
REGISTRY=""
PUSH=false
SKIP_TAG=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage:
  bash scripts/release/release.sh [--version v2.0.1] [--registry registry.example.com/ns] [--push] [--no-push] [--skip-tag] [--dry-run]

Description:
  1) 检查工作区是否干净
  2) 自动生成版本号（如果未指定）
  3) 构建多个 Docker 镜像并打上版本标签
  3) 创建对应 git annotated tag（可选）
  4) 需要时推送镜像与 tag

Images built:
  - enterprise-rag-v2-web:VERSION
  - enterprise-rag-v2-worker:VERSION
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --push) PUSH=true; shift ;;
    --no-push) PUSH=false; shift ;;
    --skip-tag) SKIP_TAG=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found"
  exit 1
fi

if [[ "$DRY_RUN" = false && "$SKIP_TAG" = false && "$PUSH" = false ]]; then
  echo "ERROR: immutable release tags require --push so registry digests can be recorded before tagging."
  echo "       Use --skip-tag for a local build, or provide --push with --registry."
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: git working tree is not clean. Please commit/stash first."
  exit 1
fi

# 自动生成版本号（如果未指定）
if [[ -z "$VERSION" ]]; then
  TIMESTAMP="$(date +"%Y%m%d%H%M")"
  ALL_TAGS=$(git tag -l "v[0-9]*.[0-9]*.[0-9]*" "v[0-9]*.[0-9]*.[0-9]*_*")

  if [[ -z "$ALL_TAGS" ]]; then
    BASE_VERSION="v1.0.0"
  else
    VERSIONS=()
    for tag in $ALL_TAGS; do
      version=${tag#v}
      version=${version%%_*}
      VERSIONS+=($version)
    done
    LATEST_VERSION=$(printf "%s\n" "${VERSIONS[@]}" | sort -V | tail -n 1)
    IFS='.' read -r MAJOR MINOR PATCH <<< "$LATEST_VERSION"
    NEW_PATCH=$((PATCH + 1))
    BASE_VERSION="v${MAJOR}.${MINOR}.${NEW_PATCH}"
  fi

  VERSION="${BASE_VERSION}_${TIMESTAMP}"
  echo "Auto-generated version: ${VERSION}"
fi

GIT_COMMIT="$(git rev-parse --short HEAD)"
GIT_SHA_FULL="$(git rev-parse HEAD)"
BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

WEB_IMAGE_NAME="enterprise-rag-v2-web"
WEB_FULL_IMAGE="${WEB_IMAGE_NAME}"
if [[ -n "$REGISTRY" ]]; then
  WEB_FULL_IMAGE="${REGISTRY}/${WEB_IMAGE_NAME}"
fi
echo "==> Building web image ${WEB_FULL_IMAGE}:${VERSION}"
if [[ "$DRY_RUN" = false ]]; then
  docker build \
    --build-arg APP_VERSION="${VERSION}" \
    --build-arg IMAGE_TAG="${VERSION}" \
    --build-arg RELEASE_GIT_SHA="${GIT_SHA_FULL}" \
    --label org.opencontainers.image.version="${VERSION}" \
    --label org.opencontainers.image.revision="${GIT_COMMIT}" \
    --label org.opencontainers.image.created="${BUILD_TIME}" \
    --label org.opencontainers.image.source="$(git config --get remote.origin.url || true)" \
    -t "${WEB_FULL_IMAGE}:${VERSION}" \
    -t "${WEB_FULL_IMAGE}:latest" \
    .
else
  echo "[DRY_RUN] Would run: docker build for ${WEB_FULL_IMAGE}"
fi

WORKER_IMAGE_NAME="enterprise-rag-v2-worker"
WORKER_FULL_IMAGE="${WORKER_IMAGE_NAME}"
if [[ -n "$REGISTRY" ]]; then
  WORKER_FULL_IMAGE="${REGISTRY}/${WORKER_IMAGE_NAME}"
fi
echo "==> Building worker image ${WORKER_FULL_IMAGE}:${VERSION}"
if [[ "$DRY_RUN" = false ]]; then
  docker build \
    --build-arg APP_VERSION="${VERSION}" \
    --build-arg IMAGE_TAG="${VERSION}" \
    --build-arg RELEASE_GIT_SHA="${GIT_SHA_FULL}" \
    --label org.opencontainers.image.version="${VERSION}" \
    --label org.opencontainers.image.revision="${GIT_COMMIT}" \
    --label org.opencontainers.image.created="${BUILD_TIME}" \
    --label org.opencontainers.image.source="$(git config --get remote.origin.url || true)" \
    -t "${WORKER_FULL_IMAGE}:${VERSION}" \
    -t "${WORKER_FULL_IMAGE}:latest" \
    .
else
  echo "[DRY_RUN] Would run: docker build for ${WORKER_FULL_IMAGE}"
fi

if [[ "$PUSH" = true ]]; then
  echo "==> Pushing web image tags"
  if [[ "$DRY_RUN" = false ]]; then
    docker push "${WEB_FULL_IMAGE}:${VERSION}"
  else
    echo "[DRY_RUN] Would run: docker push ${WEB_FULL_IMAGE}:${VERSION}"
  fi
  echo "==> Pushing worker image tags"
  if [[ "$DRY_RUN" = false ]]; then
    docker push "${WORKER_FULL_IMAGE}:${VERSION}"
  else
    echo "[DRY_RUN] Would run: docker push ${WORKER_FULL_IMAGE}:${VERSION}"
  fi
else
  echo "==> Skipping push (--no-push or default)"
fi

if [[ "$SKIP_TAG" = false ]]; then
  if [[ "$DRY_RUN" = true ]]; then
    echo "[DRY_RUN] Would resolve pushed registry digests, run verify-candidate.sh, create an annotated tag, and push it"
  else
    if git rev-parse -q --verify "refs/tags/${VERSION}" >/dev/null; then
      echo "ERROR: git tag ${VERSION} already exists"
      exit 1
    fi

    WEB_DIGEST_REF="$(docker image inspect "${WEB_FULL_IMAGE}:${VERSION}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
    WORKER_DIGEST_REF="$(docker image inspect "${WORKER_FULL_IMAGE}:${VERSION}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
    if [[ -z "$WEB_DIGEST_REF" || -z "$WORKER_DIGEST_REF" ]]; then
      echo "ERROR: pushed images did not expose immutable RepoDigests; refusing to create tag."
      exit 1
    fi

    export WEB_IMAGE="$WEB_DIGEST_REF"
    export WORKER_IMAGE="$WORKER_DIGEST_REF"
    export RELEASE_GIT_SHA="$(git rev-parse HEAD)"
    echo "==> Verifying candidate profile and deployment evidence"
    bash scripts/release/verify-candidate.sh

    echo "==> Creating annotated git tag ${VERSION}"
    git tag -a "${VERSION}" -m "Release ${VERSION}

Web image: ${WEB_IMAGE}
Worker image: ${WORKER_IMAGE}
Commit: ${RELEASE_GIT_SHA}
"
    echo "==> Pushing git tag ${VERSION}"
    git push origin "${VERSION}"
  fi
fi

echo "Release done."
echo "Web image: ${WEB_FULL_IMAGE}:${VERSION}"
echo "Worker image: ${WORKER_FULL_IMAGE}:${VERSION}"
if [[ "$SKIP_TAG" = false ]]; then
  echo "Git tag: ${VERSION}"
fi
