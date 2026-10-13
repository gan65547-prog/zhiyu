# Release Process Documentation

## Overview

This document describes the complete multi-stage release process for the enterprise-rag-v2 project:

```
Local Development → Candidate Tag → Single-host Deployment → Validation → Release Tag
```

## Release Stages

### Stage 1: Local Development
- Feature branches with regular commits
- Local testing with `docker-compose.yml`
- Code review via pull requests
- Merge to `main` branch after approval

### Stage 2: Git Tagging & Staging Release
- Create git tag with semantic versioning
- Automatic tag format: `staging-v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{git_sha8}`
- Example: `staging-v2.0.21_202604211234_abc12345`

### Stage 3: Staging Deployment (operator-provided target)
- Build Docker images locally
- Transfer images to staging server
- Deploy using docker-compose
- Run health checks (30 retries, 2-second intervals)
- All services must be healthy before proceeding

### Stage 4: Staging Validation
- Run comprehensive test suite
- Validate all API endpoints
- Test core business workflows
- Check dependencies (database, cache, vector store)
- Generate validation report
- **Must pass 100% of tests before production promotion**

### Stage 5: Production Deployment (separately configured target)
- Manual approval required after staging passes
- Create production tag: `release-v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{git_sha8}`
- Backup current production .env and compose files
- Transfer images to the single deployment host
- Deploy to production
- Run health checks (same as staging)
- Automatic rollback if health checks fail
- Update DEPLOYMENT_LOG.md

### Stage 6: Post-Deployment Verification
- Monitor error rates and logs
- Verify user-facing functionality
- Check metrics and performance
- Document release details

## Complete Release Workflow

### Prerequisite Checklist
- [ ] All code changes merged to `main`
- [ ] All CI/CD tests passing
- [ ] Database migrations are idempotent and tested
- [ ] No breaking changes to API
- [ ] Documentation updated

### Step 1: Create Staging Tag
```bash
cd enterprise-rag-v2
bash scripts/release/create-staging-tag.sh 2.0.21
```

### Step 2: Deploy to Staging
```bash
bash scripts/deploy/deploy-to-staging.sh staging-v2.0.21_202604211234_abc12345
```

### Step 3: Validate Staging Deployment
```bash
bash scripts/test/validate-staging-deployment.sh
```

**All tests must pass before proceeding.**

### Step 4: Manual Approval
After staging validation passes:
- Review test results
- Get stakeholder approval
- Confirm database backup exists

### Step 5: Promote to Production
```bash
bash scripts/deploy/promote-staging-to-production.sh staging-v2.0.21_202604211234_abc12345
```

### Step 6: Post-Deployment Verification
```bash
# Monitor logs
ssh "${PROD_HOST}" "cd \"${PROD_DIR}\" && docker compose logs -f web"

# Check application metrics
curl "${RELEASE_BASE_URL}/metrics"
```

### Step 7: Update Deployment Log
Update DEPLOYMENT_LOG.md with release details.

## Rollback Procedures

### If Staging Deployment Fails
```bash
bash scripts/deploy/rollback-staging.sh
```

### If Production Deployment Fails
Automatic rollback occurs if health checks fail within 60 seconds.

Manual rollback:
```bash
bash scripts/deploy/rollback-production.sh
```

## Version Tagging Convention

All releases use semantic versioning with git tags:

**Staging Tags:**
```
staging-v{MAJOR}.{MINOR}.{PATCH}_{YYYYMMDDHHMM}_{GIT_SHA8}
```

**Production Tags:**
```
release-v{MAJOR}.{MINOR}.{PATCH}_{YYYYMMDDHHMM}_{GIT_SHA8}
```

## Critical Safeguards

✅ Staging tag must be created and pushed to git
✅ All staging tests must pass (100%)
✅ Manual confirmation required before production push
✅ Git tag provides full code traceability
✅ Current production .env backed up before deployment
✅ Health checks mandatory (30 retries)
✅ Automatic rollback on health check failure

---

**Last Updated:** 2026-04-21
**Version:** 1.0
**Status:** Production Ready
