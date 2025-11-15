from src.api.routes.search import router as search_router
from src.api.routes.compare import router as compare_router
from src.api.routes.summarize import router as summarize_router
from src.api.routes.books import router as books_router

__all__ = ["search_router", "compare_router", "summarize_router", "books_router"]
