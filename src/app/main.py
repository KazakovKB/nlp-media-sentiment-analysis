from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from src.app.api.routers import auth_router, sources_router, analysis_router
from src.app.ui.router import router as ui_router
from src.app.infra.mq import start_broker, stop_broker

# Определение жизненного цикла
@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_broker()
    yield
    await stop_broker()

app = FastAPI(
    title="NLP-Insight",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET"),
    same_site="lax",
    https_only=False,
)

app.include_router(ui_router)
app.include_router(auth_router)
app.include_router(sources_router)
app.include_router(analysis_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/{path:path}")
def catch_all(path: str, request: Request):
    return RedirectResponse(url="/login", status_code=302)