from pathlib import Path
from typing import Any, Union

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.app.infra.mq import enqueue_analysis_job

from src.app.ui.deps import UserContext, get_current_user_ctx_ui, get_uow
from src.app.domain.contracts.uow import UoW

from src.app.services.auth_service import AuthService
from src.app.services.sources_service import SourcesService
from src.app.services.analysis_service import AnalysisService
from src.app.domain.value_objects import AnalysisScope, DateRange
from src.app.ui.presenters.overview_presenter import present_overview

# templates
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])

# Helpers
CtxOrResp = Union[UserContext, Response]


def _format_dt(value: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not value:
        return "—"
    return value.astimezone().strftime(fmt)


def _source_names(source_ids: list[int], sources_map: dict[int, str]) -> str:
    return ", ".join(sources_map.get(int(i), "—") for i in source_ids)


templates.env.filters["source_names"] = _source_names
templates.env.filters["format_dt"] = _format_dt


def _ctx(ctx_or_resp: CtxOrResp) -> CtxOrResp:
    """
    Если dependency вернула Response (RedirectResponse / HX-Redirect response),
    просто пробрасываем её из роутера. Иначе UserContext.
    """
    return ctx_or_resp


def _render(request: Request, name: str, ctx: dict[str, Any]) -> HTMLResponse:
    base = {"request": request}
    base.update(ctx)
    return templates.TemplateResponse(name, base)


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _parse_dt_iso(s: str) -> datetime:
    """
    UI форма отдаёт ISO-строку (например '2025-12-01T00:00').
    Приводим к aware UTC.
    """
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_sources_map(uow: UoW, account_id: int) -> dict[int, str]:
    sources = SourcesService(uow).list_sources(account_id)
    return {int(s.id): str(s.name) for s in sources}


# Auth UI
@router.get("/login", response_class=HTMLResponse)
def ui_login_get(request: Request):
    return _render(request, "auth/login.html", {"error": None})


@router.post("/login")
def ui_login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    uow: UoW = Depends(get_uow),
):
    svc = AuthService(uow)

    try:
        token = svc.login(email=email, password=password)
    except Exception as e:
        return _render(request, "auth/login.html", {"error": str(e)})

    request.session["access_token"] = token
    request.session["role"] = "member"
    return _redirect("/sources")


@router.get("/register", response_class=HTMLResponse)
def ui_register_get(request: Request):
    return _render(request, "auth/register.html", {"error": None})


@router.post("/register")
def ui_register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    account_name: str = Form(...),
    uow: UoW = Depends(get_uow),
):
    svc = AuthService(uow)

    try:
        token = svc.register(email=email, password=password, account_name=account_name)
    except Exception as e:
        return _render(request, "auth/register.html", {"error": str(e)})

    request.session["access_token"] = token
    request.session["role"] = "owner"
    return _redirect("/sources")


@router.post("/logout")
def ui_logout(request: Request):
    request.session.clear()
    return _redirect("/login")


# Sources UI
@router.get("/sources", response_class=HTMLResponse)
def ui_sources_list(
    request: Request,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    sources = SourcesService(uow).list_sources(ctx.account_id)
    return _render(
        request,
        "sources/list.html",
        {"ctx": ctx, "sources": sources, "active": "sources"},
    )


@router.get("/sources/{source_id}/stats", response_class=HTMLResponse)
def ui_source_stats_partial(
    request: Request,
    source_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    st = SourcesService(uow).source_stats(ctx.account_id, source_id)
    return _render(
        request,
        "sources/_stats.html",
        {"ctx": ctx, "source_id": source_id, "stats": st},
    )


# Analysis / Jobs UI
@router.get("/analysis/new", response_class=HTMLResponse)
def ui_analysis_new(
    request: Request,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    sources = SourcesService(uow).list_sources(ctx.account_id)

    now = datetime.now(timezone.utc)
    d_to = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d_from = d_to - timedelta(days=7)

    return _render(
        request,
        "analysis/new.html",
        {
            "ctx": ctx,
            "sources": sources,
            "default_from": d_from.isoformat(timespec="minutes").replace("+00:00", ""),
            "default_to": d_to.isoformat(timespec="minutes").replace("+00:00", ""),
            "error": None,
            "active": "analysis",
        },
    )


@router.post("/analysis/jobs")
async def ui_analysis_create_job(
    request: Request,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    form = await request.form()

    def _render_error(msg: str) -> HTMLResponse:
        sources = SourcesService(uow).list_sources(ctx.account_id)
        return _render(
            request,
            "analysis/new.html",
            {
                "ctx": ctx,
                "sources": sources,
                "default_from": form.get("date_from"),
                "default_to": form.get("date_to"),
                "error": msg,
                "active": "analysis",
            },
        )

    try:
        sids = [int(x) for x in form.getlist("source_ids")]
        if not sids:
            raise ValueError("Не выбран ни один источник")

        dr = DateRange(
            start=_parse_dt_iso(form.get("date_from", "")),
            end=_parse_dt_iso(form.get("date_to", "")),
        )
        if dr.start > dr.end:
            raise ValueError("Дата 'с' должна быть меньше или равна дате 'по'")

        scope = AnalysisScope(
            source_ids=sids,
            date_range=dr,
            query=(form.get("query") or None),
        )

    except Exception as e:
        return _render_error(f"Некорректные данные формы: {e}")

    svc = AnalysisService(uow)

    try:
        job = await run_in_threadpool(svc.create_job, ctx.account_id, scope)
    except ValueError as e:
        return _render_error(str(e))
    except Exception as e:
        return _render_error(f"Не удалось создать задачу: {e}")

    try:
        await enqueue_analysis_job({"job_id": job.id})
    except Exception as e:
        try:
            uow.analysis.set_error(job.id, f"mq_publish_error: {e}")
            uow.commit()
        except Exception:
            uow.rollback()

        return _render_error(
            f"Задача #{job.id} создана, но не удалось поставить в очередь (RabbitMQ недоступен). "
            f"Повторите попытку позже."
        )

    return _redirect(f"/jobs/{job.id}")


@router.get("/jobs", response_class=HTMLResponse)
def ui_jobs_list(
    request: Request,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    jobs = AnalysisService(uow).list_jobs(ctx.account_id, limit=50)
    return _render(
        request,
        "jobs/list.html",
        {"ctx": ctx, "jobs": jobs, "active": "jobs"},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def ui_job_detail(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)
    if not job:
        return _render(request, "jobs/detail.html", {"ctx": ctx, "job": None, "job_id": job_id, "active": "jobs"})

    sources_map = _build_sources_map(uow, ctx.account_id)

    return _render(
        request,
        "jobs/detail.html",
        {
            "ctx": ctx,
            "job": job,
            "job_id": job_id,
            "sources_map": sources_map,
            "active": "jobs",
        },
    )


@router.get("/jobs/{job_id}/card", response_class=HTMLResponse)
def ui_job_card_partial(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)

    sources_map = _build_sources_map(uow, ctx.account_id)

    return _render(request, "jobs/_card.html", {"ctx": ctx, "job": job, "sources_map": sources_map})


# polling-блок
@router.get("/jobs/{job_id}/overview-block", response_class=HTMLResponse)
def ui_job_overview_block_partial(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)

    sources_map = _build_sources_map(uow, ctx.account_id)

    if not job:
        return _render(
            request,
            "jobs/_overview_block.html",
            {
                "ctx": ctx,
                "job": None,
                "job_id": job_id,
                "overview": None,
                "sources_map": sources_map,
                "trends": [],
            },
        )

    overview = svc.get_overview(ctx.account_id, job_id)
    overview_v = present_overview(overview) if overview else None
    trends = svc.get_trends(ctx.account_id, job_id)

    return _render(
        request,
        "jobs/_overview_block.html",
        {
            "ctx": ctx,
            "job": job,
            "job_id": job_id,
            "overview": overview_v,
            "sources_map": sources_map,
            "trends": trends,
        },
    )


# JSON для Chart.js (ряд + overlay точек)
@router.get("/jobs/{job_id}/series")
def ui_job_series(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)
    if not job:
        return JSONResponse(
            {"labels": [], "values": [], "points": [], "status": "NOT_FOUND"},
            status_code=404,
        )

    overview = svc.get_overview(ctx.account_id, job_id)

    labels: list[str] = []
    values: list[int] = []
    points: list[dict[str, Any]] = []

    if overview and overview.metrics and overview.metrics.get("daily_series"):
        series = overview.metrics["daily_series"]
        labels = [str(x.get("ts", ""))[:10] for x in series]
        values = [int(x.get("value", 0)) for x in series]

        events = svc.get_trends(ctx.account_id, job_id)
        for ev in events:
            # baseline/z могут быть None — страхуемся
            baseline = float(ev.baseline) if ev.baseline is not None else 0.0
            z = float(ev.z) if getattr(ev, "z", None) is not None else 0.0

            points.append(
                {
                    "x": ev.ts.date().isoformat(),
                    "y": float(ev.value),
                    "kind": str(ev.kind),
                    "z": z,
                    "baseline": baseline,
                }
            )

    return {"labels": labels, "values": values, "points": points, "status": job.status}


# JSON для таблицы трендов
@router.get("/jobs/{job_id}/trends")
def ui_job_trends(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)
    if not job:
        return JSONResponse({"events": [], "status": "NOT_FOUND"}, status_code=404)

    events = svc.get_trends(ctx.account_id, job_id)

    out: list[dict[str, Any]] = []
    for e in events:
        value = float(e.value)

        baseline_val = e.baseline
        baseline = float(baseline_val) if baseline_val is not None else None

        z = float(e.z) if getattr(e, "z", None) is not None else 0.0

        if baseline is None:
            delta = None
            delta_pct = None
        else:
            delta = value - baseline
            delta_pct = (delta / baseline * 100.0) if baseline != 0 else None

        out.append(
            {
                "ts": e.ts.isoformat(),
                "date": e.ts.date().isoformat(),
                "kind": str(e.kind),
                "value": value,
                "baseline": baseline,
                "z": z,
                "delta": float(delta) if delta is not None else None,
                "delta_pct": float(delta_pct) if delta_pct is not None else None,
            }
        )

    return {"status": job.status, "events": out}


@router.get("/jobs/{job_id}/report", response_class=HTMLResponse)
def ui_job_report(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)
    if not job:
        return _render(request, "jobs/report.html", {"ctx": ctx, "job": None, "job_id": job_id})

    overview = svc.get_overview(ctx.account_id, job_id)
    overview_v = present_overview(overview) if overview else None

    sources_map = _build_sources_map(uow, ctx.account_id)
    trends = svc.get_trends(ctx.account_id, job_id)

    return _render(
        request,
        "jobs/report.html",
        {
            "ctx": ctx,
            "job": job,
            "job_id": job_id,
            "overview": overview_v,
            "sources_map": sources_map,
            "trends": trends,
            "active": "jobs",
        },
    )

@router.get("/jobs/{job_id}/panel", response_class=HTMLResponse)
def ui_job_panel_partial(
    request: Request,
    job_id: int,
    ctx_or_resp: CtxOrResp = Depends(get_current_user_ctx_ui),
    uow: UoW = Depends(get_uow),
):
    ctx = _ctx(ctx_or_resp)
    if isinstance(ctx, Response):
        return ctx

    svc = AnalysisService(uow)
    job = svc.get_job(ctx.account_id, job_id)
    sources_map = _build_sources_map(uow, ctx.account_id)

    return _render(
        request,
        "jobs/_job_panel.html",
        {"ctx": ctx, "job": job, "job_id": job_id, "sources_map": sources_map},
    )