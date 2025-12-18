from src.app.api.routers.auth import router as auth_router
from src.app.api.routers.sources import router as sources_router
from src.app.api.routers.analysis import router as analysis_router

__all__ = ["auth_router", "sources_router", "analysis_router"]