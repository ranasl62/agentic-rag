# Phase 2: Rate Limiting + Redis Caching — Plan and Specification

This document is the specification for Phase 2. It defines the execution plan, config, and behavior for rate limiting and caching.

---

## 1. Goals

- **Rate limiting:** Protect the API from abuse; per-tenant (and optional per-IP) limits; return 429 with Retry-After when exceeded.
- **Caching:** Reduce load for repeated search (and optionally query) requests; tenant-scoped keys; configurable TTL.

---

## 2. Execution Plan (Order of Development)

| # | Task | Description |
|---|------|--------------|
| 1 | **Config** | Add env-driven settings: rate limits per endpoint (search, query, upload, compare, summarize, list), optional per-IP limit, cache TTLs for search and query. |
| 2 | **Rate limit service** | Redis-based limiter: key = `rl:{endpoint}:{tenant_id}:{window}` (e.g. minute); INCR + EXPIRE; return (allowed, retry_after_seconds). |
| 3 | **Rate limit dependency** | FastAPI dependency that runs **after** auth, checks limit for the current endpoint + tenant (and optionally IP), raises 429 with Retry-After header. |
| 4 | **Wire rate limits** | Apply rate limit dependency to: POST /search, POST /query, POST /upload/document, POST /compare, POST /summarize, GET /books, GET /books/sections (each with its own limit from config). |
| 5 | **Search cache** | Before search: build key = `search:{tenant_id}:{hash(query+book_id+edition_id+limit)}`, get from Redis; on hit return cached response. On miss: run search, store result in Redis with TTL. |
| 6 | **Query cache (optional)** | Same pattern for POST /query: key = `query:{tenant_id}:{hash(query)}`, TTL shorter (e.g. 2–5 min). |
| 7 | **Cache bypass** | Optional query param or header to skip cache (e.g. `X-Skip-Cache: true` or `skip_cache=true`) for testing/freshness. |
| 8 | **Tests and validation** | Unit tests for rate limiter and cache key; integration test for 429; validation script for Phase 2. |

---

## 3. Configuration (Environment)

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_SEARCH_PER_MIN` | 100 | Max search requests per tenant per minute. |
| `RATE_LIMIT_QUERY_PER_MIN` | 20 | Max query (orchestrator) requests per tenant per minute. |
| `RATE_LIMIT_UPLOAD_PER_MIN` | 5 | Max uploads per tenant per minute. |
| `RATE_LIMIT_COMPARE_PER_MIN` | 30 | Max compare requests per tenant per minute. |
| `RATE_LIMIT_SUMMARIZE_PER_MIN` | 30 | Max summarize requests per tenant per minute. |
| `RATE_LIMIT_LIST_PER_MIN` | 60 | Max list books/sections requests per tenant per minute. |
| `RATE_LIMIT_IP_PER_MIN` | 0 | If > 0, global per-IP limit (safety net). 0 = disabled. |
| `RATE_LIMIT_ENABLED` | true | Set false to disable rate limiting. |
| `CACHE_SEARCH_TTL_SECONDS` | 300 | TTL for search cache (5 min). 0 = disable search cache. |
| `CACHE_QUERY_TTL_SECONDS` | 120 | TTL for query cache (2 min). 0 = disable query cache. |
| `CACHE_ENABLED` | true | Set false to disable all caching. |

---

## 4. Rate Limiting Details

- **Window:** Fixed 1-minute window. Key in Redis: `rl:{endpoint}:{tenant_id}:{minute_slot}` (e.g. `rl:search:uuid:202502141430`). Alternative: sliding window with sorted set; we use fixed window for simplicity.
- **Flow:** On request, dependency gets tenant from request state (after auth). It computes current minute slot, INCR key, EXPIRE key 61 seconds (so window expires). If count > limit, return 429 and set header `Retry-After: 60` (or remaining seconds in window if we track it).
- **Per-IP (optional):** If `RATE_LIMIT_IP_PER_MIN > 0`, also check key `rl:ip:{client_ip}:{minute_slot}` and reject if over limit.
- **Endpoints and limit names:** search, query, upload, compare, summarize, list (list covers both GET /books and GET /books/sections).

---

## 5. Caching Details

- **Search cache key:** `search:{tenant_id}:{sha256(query + "|" + book_id + "|" + edition_id + "|" + str(limit))}`. Value: JSON of SearchResponse (or a compact form).
- **Query cache key:** `query:{tenant_id}:{sha256(query)}`. Value: JSON of QueryResponse.
- **Skip cache:** Support query param `skip_cache=1` or header `X-Skip-Cache: true` so clients can force a fresh result.
- **Stale:** After TTL, key expires; next request is a miss and repopulates. No explicit invalidation for re-ingestion; short TTL is sufficient.

---

## 6. Files to Touch

- `config/settings.py` — Add Phase 2 settings.
- `src/api/rate_limit.py` — Rate limit logic and dependency (new).
- `src/api/cache.py` — Cache key builder and get/set helpers (new).
- `src/api/routes/search.py` — Add rate limit dep, cache get/set.
- `src/api/routes/compare.py` — Add rate limit dep.
- `src/api/routes/summarize.py` — Add rate limit dep.
- `src/api/routes/upload.py` — Add rate limit dep.
- `src/api/routes/books.py` — Add rate limit dep.
- `src/api/main.py` — Add rate limit dep to /query; add query cache.
- `src/storage/redis_client.py` — Already has get/set/get_json/set_json; possibly add `incr` + `expire` helpers if needed.
- `tests/test_phase2_rate_limit_cache.py` — Tests.
- `scripts/validate_phase2_live.py` — Live validation script.
- `.env.example` — Document new vars.

---

## 7. Validation and Testing

- **Unit tests:** `tests/test_phase2_rate_limit_cache.py` — cache key consistency, rate limit disabled, 429 response shape.
- **Live validation:** With API running, `uv run python -m scripts.validate_phase2_live` (optionally `AGENT_API_KEY=...`). Checks search 200, repeat request (cache), query 200 or 429, skip_cache.
- **Manual 429 test:** Set `RATE_LIMIT_SEARCH_PER_MIN=2`, send 3 identical search requests; third should return 429 with `Retry-After` header.

---

## 8. Testing Plan (Detailed)

1. **Rate limit:** Call search (or query) more than limit times within 1 minute with same tenant; expect 429 and Retry-After. After window expires, expect 200 again.
2. **Cache:** Two identical search requests (same tenant, same body); second returns immediately from cache (e.g. check response has same content or a cache hit indicator if we add one).
3. **Skip cache:** Request with skip_cache=1 or X-Skip-Cache: true; then same request without; both run search; no stale from first.
4. **Disabled:** With RATE_LIMIT_ENABLED=false, no 429. With CACHE_ENABLED=false, no cache reads/writes.
