# Contributing to Agentic RAG

Thanks for your interest in contributing. This project is open source and we welcome patches, docs improvements, and feedback.

---

## How to contribute

- **Bug reports and feature ideas:** Open a [GitHub Issue](https://github.com/your-username/local-ai-agent/issues) (replace with your repo URL). Describe what you did, what you expected, and what happened (and your env: OS, Python version, Docker if relevant).
- **Code and docs:** Open a Pull Request. Keep changes focused; link any related issue. We’ll review and may ask for tweaks.

---

## Development setup

1. **Clone and install**

   ```bash
   git clone https://github.com/your-username/local-ai-agent.git
   cd local-ai-agent
   uv sync   # or: pip install -e ".[dev]"
   ```

2. **Environment**

   ```bash
   cp .env.example .env
   # Set at least POSTGRES_PASSWORD. Use REQUIRE_AUTH=false for local dev if you prefer.
   ```

3. **Run dependencies** (e.g. Docker)

   ```bash
   docker compose up -d postgres qdrant redis
   ```

4. **Run the API**

   ```bash
   uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for full setup, code layout, and how to extend the system.

---

## Testing

- **Unit tests:** `uv run pytest tests/ -v --tb=short`
- **Live validation** (with stack running at http://localhost:8080):  
  `uv run python -m scripts.validate_phase1_live` … `validate_phase6_live`

See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for details.

---

## Code style

- Python: type hints where helpful; async for I/O-bound paths.
- All data and search are **tenant-scoped**; never bypass `tenant_id` in DB or Qdrant.
- New API routes: add tests or validation coverage where possible.

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT). See [LICENSE](LICENSE).
