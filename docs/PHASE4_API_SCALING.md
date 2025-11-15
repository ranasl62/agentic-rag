# Phase 4: API Scaling (Replicas + Load Balancer)

**Goal:** Run multiple API instances behind a load balancer to handle 60k dealers and concurrent traffic.

---

## 4.1 Stateless API (audit)

The API must be **stateless**: no in-memory session or per-process state that must be shared across replicas.

### Findings

| Area | Implementation | Stateless? |
|------|----------------|------------|
| **Auth** | Per-request: `X-API-Key` (or default tenant when `REQUIRE_AUTH=false`). Tenant resolved from Postgres each request; stored only in `request.state` for the duration of that request. | Yes |
| **Cache** | Redis (`get_search_cached`, `set_search_cached`, `get_query_cached`, `set_query_cached`). Shared across all replicas. | Yes |
| **Rate limit** | Redis (per tenant, per endpoint, per minute). Shared across all replicas. | Yes |
| **Data** | Postgres (books, sections, tenants) and Qdrant (vectors). All replicas use same DBs. | Yes |
| **Client singletons** | `_redis_client`, `_qdrant_storage`, `_engine`, `_async_session_factory`, `_embedding_service`, `_chat_client`, `_ollama_client` are **per-process** lazy singletons (connection pools / clients). They do not hold request- or user-specific state; any replica can serve any request. | Yes |

**Conclusion:** The API is stateless. Any replica can serve any request; auth, cache, and rate limit are per-request or backed by shared Redis/Postgres.

---

## 4.2 Load balancer

- **Role:** Reverse proxy in front of the API; single public port; health-aware routing; optional TLS.
- **Choice:** Nginx (widely used, simple config, good for Docker).

### Behaviour

- **Upstream:** `api-service:8000`. With Docker Compose `--scale api-service=N`, the service name resolves to multiple container IPs; Docker’s internal DNS round-robins. Nginx proxies to that hostname and thus across replicas.
- **Health:** Existing `GET /health` is used by Docker for `api-service` healthchecks. Nginx can use `proxy_next_upstream http_500 http_502 http_503` so failed backends are skipped.
- **TLS:** Terminate at Nginx (recommended) or at the API. For local/dev, TLS is optional; for production, configure `ssl_certificate` / `ssl_certificate_key` in the Nginx server block.

### Files

- **`docker/nginx.conf`** – Upstream, proxy pass, timeouts, and optional health-based `proxy_next_upstream`.
- **`docker-compose.yml`** – New `nginx` service; traffic to API goes through Nginx; `api-service` no longer publishes host port when using Nginx (avoids port conflict when scaling).

---

## 4.3 Running multiple API replicas

- **Docker Compose (no Swarm):**  
  `docker compose up -d --scale api-service=2` (or 3). Do **not** publish `api-service` ports when scaling; only Nginx publishes the API port.
- **Kubernetes / Cloud:** Use a Deployment with `replicas: N` and a Service in front; same stateless API image.

### Replica count (guidance)

- Start with **2** for HA; increase based on load (e.g. target CPU or latency).
- For 60k dealers, assume a small fraction concurrent (e.g. 1–5%): hundreds to low thousands of concurrent requests; tune with load tests.

---

## 4.4 Session affinity

- **Not required** for this RAG API (stateless). If you add sticky sessions later (e.g. for other features), configure them at the LB (e.g. Nginx `ip_hash` or cookie-based).

---

## 4.5 Deliverables

- [x] Confirm API is stateless (audit in this doc).
- [x] Add Nginx LB with health check and `proxy_next_upstream` for 5xx.
- [x] Docker Compose: Nginx in front; `api-service` without published port; scale with `--scale api-service=N`.
- [x] Docs: replica count, scaling, LB config (this doc + roadmap).
- [x] Validation: script or steps to verify traffic reaches replicas and auth/tenant isolation still work.

---

## 4.6 How to run (Docker Compose)

**Single API replica (default):**
```bash
docker compose up -d
# API via Nginx: http://localhost:8080 (or API_PORT from .env)
```

**Multiple API replicas (Phase 4 scaling):**
```bash
docker compose up -d --scale api-service=2
# Or 3: --scale api-service=3
# Traffic to http://localhost:8080 is load-balanced across replicas.
```

**Validate:** `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase4_live`

---

## 4.7 Configuration summary

| Item | Value |
|------|--------|
| API port (internal) | 8000 |
| Nginx listen | 80 (container) |
| Host API port | `API_PORT` (default 8080 when using Nginx) |
| Scale | `docker compose up -d --scale api-service=2` |
| Health | `GET /health` (used by Docker and Nginx `proxy_next_upstream`) |

---

## 4.8 TLS (production)

In production, add to the Nginx `server` block:

```nginx
listen 443 ssl;
ssl_certificate     /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

Mount certs or use a secret store. Keep `listen 80` for redirect or health if needed.
