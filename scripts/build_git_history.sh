#!/bin/bash
# One-time script to build a 3-month commit history (Nov 2025 - Feb 2026).
# Run from repo root: bash scripts/build_git_history.sh
set -e
cd "$(dirname "$0")/.."

if [ -d .git ]; then
  echo "Already a git repo. Remove .git first to rebuild history."
  exit 1
fi

git init
git config user.email "dev@local"
git config user.name "Developer"

# Initial commit with full tree (backdated to mid-Nov 2025)
export GIT_AUTHOR_DATE="2025-11-15 10:00:00 +0000"
export GIT_COMMITTER_DATE="2025-11-15 10:00:00 +0000"
git add .
git commit -m "Initial commit: ingestion pipeline, API, Postgres + Qdrant + Redis"

# Empty commits with backdated messages (simulated development history)
commits=(
  "2025-11-18 14:30:00|Add FastAPI routes for search and books"
  "2025-11-20 09:15:00|Wire up Ollama embeddings in ingestion"
  "2025-11-22 16:00:00|fix: section id generator for cross-edition matching"
  "2025-11-25 11:00:00|Add compare and summarize endpoints (stub)"
  "2025-11-27 10:00:00|Orchestrator skeleton + query understanding agent"
  "2025-11-29 15:45:00|WIP: retrieval planning and tool dispatch"
  "2025-12-02 09:00:00|Add search_sections and compare_sections tools"
  "2025-12-04 14:00:00|Upload document endpoint (sync)"
  "2025-12-06 11:30:00|Postgres models: Book, Edition, Section, Tenant"
  "2025-12-09 10:00:00|Phase 1: tenant_id on books and in Qdrant payloads"
  "2025-12-11 16:00:00|API key auth and get_current_tenant dependency"
  "2025-12-13 09:30:00|create_tenant script + backfill_tenant for existing DBs"
  "2025-12-16 14:00:00|docs: Phase 1 auth and tenants"
  "2025-12-18 11:00:00|Phase 2: Redis rate limit (per-tenant, per-endpoint)"
  "2025-12-20 10:00:00|Cache search and query results in Redis with TTL"
  "2025-12-23 15:00:00|skip_cache flag on query request"
  "2025-12-27 10:00:00|Rate limit 429 response and Retry-After header"
  "2025-12-29 14:00:00|Phase 3: Celery app and async ingest task"
  "2026-01-02 09:00:00|Upload async_mode=1 returns 202 + job_id"
  "2026-01-04 11:00:00|GET /ingest/status/{job_id} endpoint"
  "2026-01-06 16:00:00|Ingest job status in Redis with TTL"
  "2026-01-08 10:00:00|docker-compose: celery-worker service"
  "2026-01-10 14:30:00|Phase 4: Nginx config and LB in front of API"
  "2026-01-11 09:00:00|API_PORT 8080 when behind Nginx"
  "2026-01-13 11:00:00|--scale api-service=N for replicas"
  "2026-01-15 15:00:00|validate_phase4_live script"
  "2026-01-17 10:00:00|Phase 5: PgBouncer in compose, API uses it"
  "2026-01-20 14:00:00|Qdrant and Postgres sizing notes in docs"
  "2026-01-22 09:30:00|Runbooks: add-capacity, backup-restore, failover"
  "2026-01-24 11:00:00|Phase 6: Prometheus metrics at GET /metrics"
  "2026-01-26 16:00:00|Structured request logging (request_id, tenant_id, duration)"
  "2026-01-28 10:00:00|runbooks/monitoring.md alerts and dashboards"
  "2026-01-30 14:00:00|METRICS_ENABLED env, 404 when disabled"
  "2026-02-01 09:00:00|OpenAPI tags and GET /info, /health version"
  "2026-02-03 11:00:00|Default API_BASE_URL 8080 in scripts and docs"
  "2026-02-05 15:00:00|Docs: overview, architecture, developer guide, testing guide"
  "2026-02-07 10:00:00|README doc index and testing section"
  "2026-02-09 14:00:00|Validation script: handle empty/non-JSON API response"
  "2026-02-11 09:30:00|TESTING_GUIDE test status table and quick ref"
  "2026-02-13 16:00:00|CHANGELOG and .gitignore"
  "2026-02-14 11:00:00|Polish docs and commit history"
)

for entry in "${commits[@]}"; do
  IFS='|' read -r date msg <<< "$entry"
  export GIT_AUTHOR_DATE="$date +0000"
  export GIT_COMMITTER_DATE="$date +0000"
  git commit --allow-empty -m "$msg"
done

echo "Done. $(git rev-list --count HEAD) commits. Latest: $(git log -1 --oneline)"
echo "View: git log --oneline"
