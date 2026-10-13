#!/usr/bin/env bash
# Deploy an immutable candidate to the staging host.
#
# Usage:
#   bash scripts/deploy/deploy-to-staging.sh staging-v0.2.0_202608111600_1ffc620b
#
# The script transfers only the already-built images and the checked-in
# deployment compose file. Secrets remain in the staging environment file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TAG="${1:-}"
STAGING_HOST="${STAGING_HOST:?Set STAGING_HOST=user@host}"
STAGING_PORT="${STAGING_PORT:-8000}"
STAGING_DIR="${STAGING_DIR:?Set STAGING_DIR to the project directory on the staging host}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.deploy.yml}"
STAGING_ENV_FILE="${STAGING_ENV_FILE:-.env.staging}"
SKIP_BUILD="${SKIP_BUILD:-false}"

if [[ -z "$TAG" ]]; then
    echo -e "${RED}Error: tag is required${NC}"
    exit 1
fi
if [[ ! "$TAG" =~ ^staging-v([0-9]+\.[0-9]+\.[0-9]+)_([0-9]+)_([a-f0-9]{8})$ ]]; then
    echo -e "${RED}Error: invalid staging tag: ${TAG}${NC}"
    echo "Expected staging-v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{sha8}"
    exit 1
fi
if [[ ! -f "${PROJECT_ROOT}/${COMPOSE_FILE}" ]]; then
    echo -e "${RED}Error: compose file not found: ${PROJECT_ROOT}/${COMPOSE_FILE}${NC}"
    exit 1
fi
if [[ ! -f "${PROJECT_ROOT}/${STAGING_ENV_FILE}" ]]; then
    echo -e "${RED}Error: staging env file not found: ${PROJECT_ROOT}/${STAGING_ENV_FILE}${NC}"
    exit 1
fi

VERSION="${BASH_REMATCH[1]}"
GIT_SHA_SHORT="${BASH_REMATCH[3]}"
GIT_SHA_FULL="$(git -C "$PROJECT_ROOT" rev-parse "${GIT_SHA_SHORT}^{commit}")"
if ! git -C "$PROJECT_ROOT" merge-base --is-ancestor "$GIT_SHA_FULL" HEAD; then
    echo -e "${RED}Error: candidate commit ${GIT_SHA_FULL} is not an ancestor of HEAD${NC}"
    exit 1
fi
WEB_IMAGE="enterprise-rag-v2-web:${TAG}"
WORKER_IMAGE="enterprise-rag-v2-worker:${TAG}"

echo "=========================================================="
echo "Deploying staging candidate ${TAG}"
echo "Target: ${STAGING_HOST}:${STAGING_PORT}"
echo "Commit: ${GIT_SHA_FULL}"
echo "=========================================================="

cd "$PROJECT_ROOT"

if [[ "$SKIP_BUILD" != "true" ]]; then
    echo -e "${BLUE}[1/6] Building immutable staging images${NC}"
    docker build --target runtime \
        --build-arg PRELOAD_BGE_MODEL=1 \
        --build-arg APP_VERSION="${VERSION}" \
        --build-arg IMAGE_TAG="${TAG}" \
        --build-arg RELEASE_GIT_SHA="${GIT_SHA_FULL}" \
        -t "$WEB_IMAGE" -f Dockerfile .
    docker build --target runtime \
        --build-arg PRELOAD_BGE_MODEL=0 \
        --build-arg APP_VERSION="${VERSION}" \
        --build-arg IMAGE_TAG="${TAG}" \
        --build-arg RELEASE_GIT_SHA="${GIT_SHA_FULL}" \
        -t "$WORKER_IMAGE" -f Dockerfile .
else
    echo -e "${YELLOW}[1/6] Skipping image build (SKIP_BUILD=true)${NC}"
fi
docker image inspect "$WEB_IMAGE" >/dev/null
docker image inspect "$WORKER_IMAGE" >/dev/null

echo -e "${BLUE}[2/6] Checking staging SSH and preparing directory${NC}"
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$STAGING_HOST" \
    "mkdir -p '${STAGING_DIR}/runtime/uploads' '${STAGING_DIR}/shared'"

echo -e "${BLUE}[3/6] Transferring images and deployment configuration${NC}"
docker save "$WEB_IMAGE" | ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$STAGING_HOST" "docker load"
docker save "$WORKER_IMAGE" | ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$STAGING_HOST" "docker load"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no \
    "${PROJECT_ROOT}/${COMPOSE_FILE}" "${PROJECT_ROOT}/${STAGING_ENV_FILE}" \
    "${STAGING_HOST}:${STAGING_DIR}/"

echo -e "${BLUE}[4/6] Starting the checked-in deployment compose${NC}"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$STAGING_HOST" \
    "STAGING_DIR='${STAGING_DIR}' TAG='${TAG}' WEB_IMAGE='${WEB_IMAGE}' WORKER_IMAGE='${WORKER_IMAGE}' APP_VERSION='${VERSION}' RELEASE_GIT_SHA='${GIT_SHA_FULL}' bash -s" <<'SSHEOF'
set -euo pipefail
cd "$STAGING_DIR"
if [[ -f .env ]]; then
    cp .env ".env.backup.$(date +%Y%m%d-%H%M%S)"
fi
cp .env.staging .env
export WEB_IMAGE WORKER_IMAGE APP_VERSION IMAGE_TAG="$TAG" RELEASE_GIT_SHA
docker compose --env-file .env -f docker-compose.deploy.yml down --remove-orphans || true
docker compose --env-file .env -f docker-compose.deploy.yml up -d --force-recreate
SSHEOF

echo -e "${BLUE}[5/6] Waiting for readiness${NC}"
for attempt in $(seq 1 45); do
    if curl -fsS --max-time 5 "http://${STAGING_HOST#*@}:${STAGING_PORT}/health/ready" >/dev/null; then
        echo -e "${GREEN}✓ staging readiness passed${NC}"
        break
    fi
    if [[ "$attempt" == 45 ]]; then
        echo -e "${RED}✗ staging did not become ready${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${BLUE}[6/6] Recording deployment identity${NC}"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$STAGING_HOST" \
    "cd '${STAGING_DIR}' && docker compose --env-file .env -f docker-compose.deploy.yml ps"

echo "=========================================================="
echo -e "${GREEN}Staging deployment completed${NC}"
echo "URL: http://${STAGING_HOST#*@}:${STAGING_PORT}"
echo "Tag: ${TAG}"
echo "Commit: ${GIT_SHA_FULL}"
echo "Next: run validate-staging-deployment.sh against this URL."
echo "=========================================================="
