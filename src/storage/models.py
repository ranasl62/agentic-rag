"""
SQLAlchemy models for books, editions, sections, and cross-edition alignments.
Matches the schema defined in the architecture document.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    """Declarative base for all models."""

    pass


class Tenant(Base):
    """Tenant (dealer/brand) for multi-tenant isolation."""

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    books: Mapped[List["Book"]] = relationship(
        "Book", back_populates="tenant", cascade="all, delete-orphan"
    )


class Book(Base):
    """A logical book (title + author). Multiple editions belong to one book."""

    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("title", "author", "tenant_id", name="uq_books_title_author_tenant"),
        Index("idx_books_tenant_id", "tenant_id"),
    )

    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    isbn: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="books")
    editions: Mapped[List["Edition"]] = relationship(
        "Edition", back_populates="book", cascade="all, delete-orphan"
    )


class Edition(Base):
    """A specific edition/version of a book (e.g. 2015, 2021)."""

    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint("book_id", "edition_name", name="uq_editions_book_edition"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.book_id", ondelete="CASCADE"), nullable=False
    )
    edition_name: Mapped[str] = mapped_column(Text, nullable=False)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    book: Mapped["Book"] = relationship("Book", back_populates="editions")
    sections: Mapped[List["Section"]] = relationship(
        "Section", back_populates="edition", cascade="all, delete-orphan"
    )


class Section(Base):
    """
    A section of an edition: chapter/section/subsection with content.
    canonical_section_id is stable across editions for matching.
    """

    __tablename__ = "sections"
    __table_args__ = (
        Index("idx_sections_canonical", "canonical_section_id"),
        Index("idx_sections_edition_sequence", "edition_id", "sequence_number"),
        Index("idx_sections_semantic_hash", "semantic_hash"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.edition_id", ondelete="CASCADE"), nullable=False
    )
    canonical_section_id: Mapped[str] = mapped_column(Text, nullable=False)

    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subsection_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subsection_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_path: Mapped[str] = mapped_column(Text, nullable=False)

    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False)

    semantic_hash: Mapped[str] = mapped_column(Text, nullable=False)
    heading_embedding_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    edition: Mapped["Edition"] = relationship("Edition", back_populates="sections")
    chunks: Mapped[List["SectionChunk"]] = relationship(
        "SectionChunk", back_populates="section", cascade="all, delete-orphan"
    )


class SectionChunk(Base):
    """A chunk of a section for long content; each chunk has its own embedding."""

    __tablename__ = "section_chunks"
    __table_args__ = (UniqueConstraint("section_id", "chunk_index", name="uq_chunks_section_index"),)

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_id: Mapped[str] = mapped_column(Text, nullable=False)

    section: Mapped["Section"] = relationship("Section", back_populates="chunks")


class SectionAlignment(Base):
    """Maps the same logical section across two editions (source -> target)."""

    __tablename__ = "section_alignments"
    __table_args__ = (
        Index("idx_alignments_canonical", "canonical_section_id"),
        Index("idx_alignments_source", "source_section_id"),
        Index("idx_alignments_target", "target_section_id"),
    )

    alignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_section_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False
    )
    target_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False
    )

    alignment_score: Mapped[float] = mapped_column(Float, nullable=False)
    alignment_method: Mapped[str] = mapped_column(Text, nullable=False)
    text_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    structural_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    length_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
