from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi import Request
from src.app.api.routers import auth_router, sources_router, analysis_router
from src.app.ui.router import router as ui_router
from starlette.middleware.sessions import SessionMiddleware
from src.app.infra.mq import start_broker, stop_broker
import os


app = FastAPI(
    title="NLP-Insight",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
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

@app.on_event("startup")
async def _mq_start():
    await start_broker()

@app.on_event("shutdown")
async def _mq_stop():
    await stop_broker()

@app.get("/{path:path}")
def catch_all(path: str, request: Request):
    return RedirectResponse(url="/login", status_code=302)