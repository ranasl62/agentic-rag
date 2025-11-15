# Phase 6: Monitoring, Alerts, Runbooks — Detailed Plan

**Goal:** Know when things break, why, and what to do. Runbooks are already in place (Phase 5); Phase 6 adds metrics, structured logging, and alert documentation.

---

## 6.1 Scope

| Item | Description | Status |
|------|-------------|--------|
| **Metrics** | Prometheus-style metrics: request count, latency by endpoint, status; export at `/metrics` | Implemented |
| **Structured logging** | JSON logs with `request_id`, `tenant_id` (when present), `endpoint`, `method`, `status_code`, `duration_ms` | Implemented |
| **Alerts** | Document Prometheus alert rules and channels; optional Alertmanager config | Documented |
| **Dashboards** | Document suggested Grafana panels (API latency, errors, queue) | Documented |
| **Runbooks** | add-capacity, backup-restore, failover (docs/runbooks/) | Done (Phase 5) |

---

## 6.2 Metrics (Prometheus)

### 6.2.1 API metrics

- **`http_requests_total`** — Counter, labels: `method`, `endpoint`, `status_class` (2xx, 4xx, 5xx).
- **`http_request_duration_seconds`** — Histogram, labels: `method`, `endpoint`; buckets for latency (e.g. 0.01, 0.05, 0.1, 0.5, 1, 5).
- **Endpoint:** `GET /metrics` — returns Prometheus text format; no auth (scrape by Prometheus or cloud agent). Optionally exclude from rate limit.

### 6.2.2 Queue metrics (Celery)

- Optional: expose Celery task count, success/failure from worker (e.g. via `celery inspect` or Flower). Document in this phase; implementation can be a separate worker-side export or Flower.
- For now: document that Prometheus can scrape API `/metrics`; Celery/queue metrics can be added later (Flower or custom exporter).

### 6.2.3 Implementation

- Use `prometheus_client` (Counter, Histogram, generate_latest).
- Middleware: record request start time; after response, increment counter and observe duration; set labels from request path (normalized to endpoint) and status class.

### 6.2.4 Config

- **`METRICS_ENABLED`** — default true; if false, `/metrics` returns 404 or empty.
- **`LOG_LEVEL`** — already in settings (INFO, DEBUG, etc.); used for structured logs.

---

## 6.3 Structured Logging

### 6.3.1 Requirements

- **request_id:** UUID per request; set in middleware; include in every log line for that request.
- **tenant_id:** When auth succeeded, include in request log (so logs can be filtered by tenant).
- **Fields per request log:** `request_id`, `tenant_id` (optional), `method`, `path` or `endpoint`, `status_code`, `duration_ms`, `error` (if any).

### 6.3.2 Format

- **JSON** (structlog processor) for production; configurable so dev can use console with colors.
- **When:** Log one line per request (after response) in middleware; optional per-route logs using the same request_id.

### 6.3.3 Implementation

- Middleware: generate `request_id` (uuid4), store in `request.state`; after response, build log dict with request_id, tenant_id (from request.state if set), method, path, status_code, duration_ms; call structlog.info or similar.
- Use `structlog` with JSON renderer when LOG_LEVEL and env indicate production.

---

## 6.4 Alerts (Documentation)

Document recommended alert rules (e.g. for Prometheus Alertmanager):

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High error rate | rate(http_requests_total{status_class="5xx"}[5m]) / rate(http_requests_total[5m]) > 0.05 | critical | Page on-call; check runbooks/failover |
| High latency | histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 10 | warning | Check API and dependencies |
| Service down | up{job="api"} == 0 | critical | Restart service; see failover runbook |
| Redis/Qdrant/Postgres | Document: probe or exporter down | critical | See docs/runbooks/failover.md |

Channels: PagerDuty, Slack, or email — document in runbook or ops doc.

---

## 6.5 Dashboards (Documentation)

Suggested panels for Grafana (or cloud dashboard):

- **Request rate:** rate(http_requests_total[1m]) by endpoint.
- **Error rate:** rate of 5xx / rate of all requests.
- **Latency p50/p95/p99:** histogram_quantile from http_request_duration_seconds.
- **Top endpoints by latency:** table or bar chart.

---

## 6.6 Implementation Summary

- **Metrics:** `src/api/metrics.py` (Counter, Histogram); `GET /metrics` in main.py; middleware in `src/api/middleware/request_metrics_logging.py` records each request.
- **Logging:** Same middleware logs one JSON line per request via structlog (request_id, tenant_id, method, path, endpoint, status_code, duration_ms). Config: `src/utils/logging_config.py` (LOG_LEVEL).
- **Config:** `METRICS_ENABLED`, `LOG_LEVEL` in config/settings.py and .env.example.
- **Tests:** tests/test_phase6_metrics.py, tests/test_phase6_logging.py; scripts/validate_phase6_live.py.
- **Runbook:** docs/runbooks/monitoring.md (scrape, alert rules, dashboards, logging).

---

## 6.7 Test Cases

### 6.6.1 Metrics

| ID | Test | Type | Description |
|----|------|------|-------------|
| M1 | GET /metrics returns 200 | Unit/Live | Response status 200, Content-Type text/plain. |
| M2 | /metrics contains request counter | Unit | Response body contains `http_requests_total` or similar. |
| M3 | /metrics contains duration histogram | Unit | Response body contains `http_request_duration_seconds`. |
| M4 | Request increments counter and histogram | Unit | Call an endpoint (e.g. /health), then GET /metrics; counter and histogram show at least one observation. |

### 6.6.2 Structured logging

| ID | Test | Type | Description |
|----|------|------|-------------|
| L1 | request_id set on request.state | Unit | Middleware sets request.state.request_id (UUID string). |
| L2 | Log line contains request_id and duration | Unit | After a request, a log event (or log capture) contains request_id and duration_ms. |
| L3 | Log line contains tenant_id when authenticated | Unit | Request with valid API key produces log with tenant_id. |
| L4 | Log line contains status_code and path | Unit | Log event contains status_code and path/endpoint. |

### 6.6.3 Alerts and runbooks

| ID | Test | Type | Description |
|----|------|------|-------------|
| A1 | Runbooks exist | Doc | docs/runbooks/add-capacity.md, backup-restore.md, failover.md exist. |
| A2 | Alert rules documented | Doc | Phase 6 doc or runbook references alert conditions and channels. |

---

## 6.8 Execution Order

1. Add `prometheus_client` dependency.
2. Add metrics middleware + GET /metrics route (or mount prometheus_client's app).
3. Add structured logging middleware (request_id, optional tenant_id, log one line per request).
4. Configure structlog (JSON renderer, log_level from settings).
5. Add tests: test_phase6_metrics.py, test_phase6_logging.py (and optional validate_phase6_live.py).
6. Document alerts and dashboards in this doc or docs/runbooks/monitoring.md.
7. Update roadmap Phase 6 deliverables to [x] where done.

---

## 6.9 Files to Add/Touch

- `requirements.txt` / `pyproject.toml` — add prometheus_client.
- `src/api/main.py` — mount metrics app or add /metrics; add middleware for metrics and logging.
- `src/api/middleware/metrics.py` or `src/api/metrics.py` — define Counter/Histogram, optional middleware.
- `src/api/middleware/logging.py` — request_id, tenant_id, structlog per request.
- `src/utils/logging_config.py` or in middleware — configure structlog (JSON, level).
- `config/settings.py` — METRICS_ENABLED, ensure LOG_LEVEL used.
- `tests/test_phase6_metrics.py` — M1–M4.
- `tests/test_phase6_logging.py` — L1–L4 (may need log capture).
- `scripts/validate_phase6_live.py` — GET /metrics 200, body contains expected metric names.
- `docs/runbooks/monitoring.md` — optional; alerts and dashboards summary.
- `.env.example` — METRICS_ENABLED.
