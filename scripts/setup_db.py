"""Create database tables. Run once: python -m scripts.setup_db"""
import asyncio
import os

# Ensure project root on path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.postgres_client import init_db
from src.storage.qdrant_client import get_qdrant_storage


async def main():
    await init_db()
    print("Postgres tables created.")
    qdrant = get_qdrant_storage()
    qdrant.ensure_collections()
    print("Qdrant collections ensured.")


if __name__ == "__main__":
    asyncio.run(main())
