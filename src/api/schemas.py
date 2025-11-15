"""
Request/response schemas for the API.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    book_id: Optional[str] = None
    edition_id: Optional[str] = None
    generate_answer: bool = Field(default=False, description="If true, use Ollama to generate a short answer from the retrieved sections")
    skip_cache: bool = Field(default=False, description="If true, bypass cache and run fresh search (Phase 2)")


class CompareRequest(BaseModel):
    book_id: str
    chapter_number: Optional[int] = None
    section_number: Optional[int] = None
    canonical_section_id: Optional[str] = None
    edition_ids: Optional[List[str]] = None


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
    book_id: Optional[str] = None
    location_path: Optional[str] = None


class SearchResultItem(BaseModel):
    section_id: Optional[str] = None
    edition_id: Optional[str] = None
    book_id: Optional[str] = None
    location_path: Optional[str] = None
    content_preview: Optional[str] = None
    score: Optional[float] = None


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


class SectionInfo(BaseModel):
    section_id: str
    edition_id: str
    canonical_section_id: str
    location_path: str
    content_length: int
