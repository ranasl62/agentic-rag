"""
End-to-end ingestion: parse document → extract structure → chunk → embed → store (Postgres + Qdrant).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.section_id_generator import SectionIdGenerator
from src.ingestion.parsers.structure_extractor import StructureExtractor, SectionBlock
from src.ingestion.chunking.semantic_chunker import semantic_chunk
from src.storage.models import Book, Edition, Section, SectionChunk
from src.storage.qdrant_client import QdrantStorage, SECTION_COLLECTION, CHUNK_COLLECTION


class IngestionPipeline:
    """
    Ingest one document (e.g. PDF/EPUB) as one edition of a book.
    Caller provides raw text or list of (heading, content) from their parser.
    """

    def __init__(
        self,
        session: AsyncSession,
        qdrant: QdrantStorage,
        embedding_service: Any,
    ) -> None:
        self._session = session
        self._qdrant = qdrant
        self._embedding = embedding_service
        self._structure = StructureExtractor()

    async def ensure_book_and_edition(
        self,
        tenant_id: UUID,
        title: str,
        author: str,
        edition_name: str,
        publication_year: Optional[int] = None,
        publisher: Optional[str] = None,
        isbn: Optional[str] = None,
    ) -> tuple[Book, Edition]:
        """Get or create book and edition for the given tenant."""
        stmt = select(Book).where(
            Book.tenant_id == tenant_id,
            Book.title == title,
            Book.author == author,
        )
        result = await self._session.execute(stmt)
        book = result.scalars().first()
        if not book:
            book = Book(tenant_id=tenant_id, title=title, author=author, isbn=isbn)
            self._session.add(book)
            await self._session.flush()
        version_hash = hashlib.sha256(f"{title}|{author}|{edition_name}".encode()).hexdigest()[:32]
        stmt = select(Edition).where(Edition.book_id == book.book_id, Edition.edition_name == edition_name)
        result = await self._session.execute(stmt)
        edition = result.scalars().first()
        if not edition:
            edition = Edition(
                book_id=book.book_id,
                edition_name=edition_name,
                publication_year=publication_year,
                publisher=publisher,
                version_hash=version_hash,
            )
            self._session.add(edition)
            await self._session.flush()
        return book, edition

    async def ingest_from_blocks(
        self,
        book: Book,
        edition: Edition,
        blocks: List[SectionBlock],
    ) -> List[Section]:
        """Turn section blocks into Section + SectionChunk rows and vectors."""
        book_slug = f"book_{str(book.book_id).replace('-', '')[:8]}"
        gen = SectionIdGenerator(book_slug)
        sections: List[Section] = []
        for block in blocks:
            loc_path = gen.location_path(
                block.chapter_number,
                block.chapter_title,
                block.section_number,
                block.section_title,
                block.subsection_number,
                block.subsection_title,
            )
            canonical_id = gen.canonical_section_id(
                chapter_number=block.chapter_number,
                chapter_title=block.chapter_title,
                section_number=block.section_number,
                section_title=block.section_title,
                subsection_number=block.subsection_number,
                subsection_title=block.subsection_title,
                sequence_number=block.sequence_number,
            )
            sem_hash = gen.semantic_hash(loc_path, block.section_title or block.chapter_title or "", block.content[:500])
            content = block.content.strip() or "(no content)"
            section = Section(
                section_id=uuid4(),
                edition_id=edition.edition_id,
                canonical_section_id=canonical_id,
                chapter_number=block.chapter_number,
                chapter_title=block.chapter_title,
                section_number=block.section_number,
                section_title=block.section_title,
                subsection_number=block.subsection_number,
                subsection_title=block.subsection_title,
                location_path=loc_path,
                sequence_number=block.sequence_number,
                content_text=content,
                content_length=len(content),
                semantic_hash=sem_hash,
                chunk_count=1,
            )
            self._session.add(section)
            await self._session.flush()

            # Heading embedding for section-level search
            heading_text = f"{loc_path}: {block.section_title or block.chapter_title or 'Section'}"
            try:
                vec = self._embedding.embed(heading_text + "\n" + content[:500])
            except Exception:
                vec = self._embedding.embed(".")
            point_id = str(section.section_id).replace("-", "")
            section.heading_embedding_id = point_id
            self._qdrant.upsert_section_vector(
                point_id,
                vec,
                {
                    "section_id": str(section.section_id),
                    "edition_id": str(edition.edition_id),
                    "book_id": str(book.book_id),
                    "tenant_id": str(book.tenant_id),
                    "canonical_section_id": canonical_id,
                    "location_path": loc_path,
                    "chapter_number": block.chapter_number,
                    "section_number": block.section_number,
                    "content_preview": content[:200],
                    "embedding_type": "heading",
                    "token_count": len(content.split()),
                },
            )
            chunks = semantic_chunk(content)
            section.chunk_count = len(chunks)
            for idx, chunk_text in enumerate(chunks):
                try:
                    cvec = self._embedding.embed(chunk_text)
                except Exception:
                    cvec = self._embedding.embed(".")
                chunk_id = uuid4()
                cpoint_id = str(chunk_id).replace("-", "")
                self._session.add(
                    SectionChunk(
                        chunk_id=chunk_id,
                        section_id=section.section_id,
                        chunk_index=idx,
                        chunk_text=chunk_text,
                        token_count=len(chunk_text.split()),
                        embedding_id=cpoint_id,
                    )
                )
                self._qdrant.upsert_chunk_vectors([
                    (
                        cpoint_id,
                        cvec,
                        {
                            "chunk_id": str(chunk_id),
                            "section_id": str(section.section_id),
                            "edition_id": str(edition.edition_id),
                            "book_id": str(book.book_id),
                            "tenant_id": str(book.tenant_id),
                            "canonical_section_id": canonical_id,
                            "chunk_index": idx,
                            "chunk_text": chunk_text[:500],
                        },
                    )
                ])
            sections.append(section)
        return sections

    async def ingest_raw_text(
        self,
        tenant_id: UUID,
        title: str,
        author: str,
        edition_name: str,
        raw_text: str,
        publication_year: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Section]:
        """Convenience: parse raw text into lines, extract structure, ingest."""
        lines = raw_text.splitlines()
        blocks = self._structure.parse_lines(lines)
        if not blocks:
            blocks = [SectionBlock(content=raw_text, sequence_number=0)]
        book, edition = await self.ensure_book_and_edition(
            tenant_id=tenant_id,
            title=title,
            author=author,
            edition_name=edition_name,
            publication_year=publication_year,
            **kwargs,
        )
        return await self.ingest_from_blocks(book, edition, blocks)
