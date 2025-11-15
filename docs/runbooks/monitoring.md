# Runbook: Monitoring, Alerts, and Dashboards (Phase 6)

How to observe the API and queue, and what to do when alerts fire.

---

## 1. Metrics (Prometheus)

### 1.1 API metrics

The API exposes **GET /metrics** (no auth) in Prometheus text format.

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, endpoint, status_class (2xx, 4xx, 5xx) | Total requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency (buckets 0.01–10s) |

- **Endpoint:** `GET /metrics`. Returns 404 if `METRICS_ENABLED=false`.
- **Scrape:** Point Prometheus (or your cloud agent) at `http://api-host:8080/metrics` (or the API port). Scrape interval e.g. 15s.

### 1.2 Celery / queue

- Celery does not expose Prometheus metrics by default. Options:
  - **Flower:** run Flower alongside workers; it can expose metrics or a dashboard.
  - **Custom exporter:** periodic script that runs `celery inspect` and publishes queue length to Prometheus.
- For now, rely on API metrics and runbooks; add queue metrics later if needed.

---

## 2. Suggested Prometheus alert rules

Examples (adapt to your Prometheus/Alertmanager):

```yaml
# High API error rate (5xx)
- alert: HighAPIErrorRate
  expr: |
    sum(rate(http_requests_total{status_class="5xx"}[5m])) /
    sum(rate(http_requests_total[5m])) > 0.05
  for: 5m
  labels: { severity: critical }
  annotations:
    summary: "API 5xx rate above 5%"

# High latency (p95 > 10s)
- alert: HighAPILatency
  expr: |
    histogram_quantile(0.95,
      sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)
    ) > 10
  for: 5m
  labels: { severity: warning }
  annotations:
    summary: "API p95 latency above 10s"

# API down (target down)
- alert: APIDown
  expr: up{job="agentic-rag-api"} == 0
  for: 1m
  labels: { severity: critical }
  annotations:
    summary: "API target is down"
```

**Channels:** Configure Alertmanager to send to PagerDuty, Slack, or email. Document on-call and escalation in your ops wiki.

---

## 3. Suggested Grafana panels

- **Request rate:** `sum(rate(http_requests_total[1m])) by (endpoint)`
- **Error rate:** `sum(rate(http_requests_total{status_class="5xx"}[5m])) / sum(rate(http_requests_total[5m]))`
- **Latency p50/p95/p99:** `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))`
- **Top endpoints by volume:** table of `sum(rate(http_requests_total[5m])) by (endpoint)`

---

## 4. Structured logging

- Each request is logged as one JSON line (structlog) with: `request_id`, `tenant_id` (if authenticated), `method`, `path`, `endpoint`, `status_code`, `duration_ms`.
- **LOG_LEVEL:** Set via env (e.g. INFO in prod, DEBUG in staging).
- **Aggregation:** Ship logs to Loki, Elasticsearch, or cloud logging; search by `request_id` or `tenant_id` for debugging.

---

## 5. When alerts fire

- **HighAPIErrorRate / 5xx:** See [failover.md](failover.md); check API and dependency (Postgres, Qdrant, Redis, Ollama).
- **HighAPILatency:** Check slow endpoints in Grafana; scale API replicas or optimize slow routes; see [add-capacity.md](add-capacity.md).
- **APIDown:** Restart API/container; see [failover.md](failover.md).
