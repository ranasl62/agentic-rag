"""
Request/response schemas for the API.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=20, ge=1, le=100, description="Number of results (default 20, max 100)")
    document_id: Optional[str] = Field(None, description="Filter by document ID")
    book_id: Optional[str] = Field(None, description="Deprecated: use document_id")
    edition_id: Optional[str] = None
    generate_answer: bool = Field(default=False, description="If true, use LLM to generate a short answer from the retrieved sections")
    include_content: bool = Field(default=False, description="If true, include full section text in each result (from Postgres)")
    skip_cache: bool = Field(default=False, description="If true, bypass cache and run fresh search (Phase 2)")


class CompareRequest(BaseModel):
    document_id: Optional[str] = Field(None, description="Document ID to compare across editions")
    book_id: Optional[str] = Field(None, description="Deprecated: use document_id")
    chapter_number: Optional[int] = None
    section_number: Optional[int] = None
    canonical_section_id: Optional[str] = None
    edition_ids: Optional[List[str]] = None

    def get_document_id(self) -> Optional[str]:
        """Preferred document ID (document_id or legacy book_id)."""
        return self.document_id or self.book_id


class SummarizeRequest(BaseModel):
    section_ids: Optional[List[str]] = Field(None, description="Specific section UUIDs")
    query: Optional[str] = Field(None, description="Or describe what to summarize")
    max_length: int = Field(default=300, ge=50, le=1000)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    skip_verification: bool = False
    skip_cache: bool = Field(default=False, description="If true, bypass query cache (Phase 2)")


class Citation(BaseModel):
    section_id: Optional[str] = None
    edition_id: Optional[str] = None
    document_id: Optional[str] = Field(None, description="Document (book) ID")
    location_path: Optional[str] = None
    book_title: Optional[str] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None


class SearchResultItem(BaseModel):
    section_id: Optional[str] = None
    edition_id: Optional[str] = None
    document_id: Optional[str] = Field(None, description="Document (book) ID")
    location_path: Optional[str] = None
    content_preview: Optional[str] = Field(None, description="Short excerpt; use content for full text when include_content=true")
    content: Optional[str] = Field(None, description="Full section text when include_content=true")
    score: Optional[float] = None
    book_title: Optional[str] = Field(None, description="Document title")
    book_author: Optional[str] = None
    edition_name: Optional[str] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None


class SearchResponse(BaseModel):
    success: bool = True
    results: List[SearchResultItem] = []
    citations: List[Citation] = []
    answer: Optional[str] = Field(default=None, description="LLM-generated answer when generate_answer=true")


class CompareResponse(BaseModel):
    success: bool = True
    sections: List[Dict[str, Any]] = []
    canonical_section_id: Optional[str] = None
    citations: List[Citation] = []


class SummarizeResponse(BaseModel):
    success: bool = True
    summary: str = ""
    citations: List[Citation] = []


class QueryResponse(BaseModel):
    response: str
    steps: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    verified: bool = False


class BookInfo(BaseModel):
    book_id: str
    title: str
    author: str
    editions: List[Dict[str, Any]]


class BooksResponse(BaseModel):
    books: List[BookInfo] = []


class DocumentInfo(BaseModel):
    document_id: str
    title: str
    author: str
    editions: List[Dict[str, Any]]


class DocumentsResponse(BaseModel):
    documents: List[DocumentInfo] = []


class SectionInfo(BaseModel):
    section_id: str
    edition_id: str
    canonical_section_id: str
    location_path: str
    content_length: int
