"""Ingest a book from a raw text file. Usage: python -m scripts.ingest_book --title "My Book" --author "Author" --edition "2021" --file path/to/book.txt"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.postgres_client import session_scope
from src.storage.qdrant_client import get_qdrant_storage
from src.llm.embeddings import get_embedding_service
from src.ingestion.ingestion_pipeline import IngestionPipeline


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--edition", required=True, help="Edition name e.g. 2021 or First Edition")
    parser.add_argument("--file", required=True, help="Path to plain text file")
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    qdrant = get_qdrant_storage()
    qdrant.ensure_collections()
    embedding = get_embedding_service()

    async with session_scope() as session:
        pipeline = IngestionPipeline(session, qdrant, embedding)
        sections = await pipeline.ingest_raw_text(
            title=args.title,
            author=args.author,
            edition_name=args.edition,
            raw_text=raw_text,
            publication_year=args.year,
        )
    print(f"Ingested {len(sections)} sections.")


if __name__ == "__main__":
    asyncio.run(main())
