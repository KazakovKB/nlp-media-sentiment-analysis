from fastapi import APIRouter, Depends, HTTPException, status

from src.app.api.deps import UserContext, get_current_user_ctx
from src.app.api.schemas import (
    CreateAnalysisJobRequest,
    AnalysisJobResponse,
    OverviewReportResponse,
    job_to_response,
)
from src.app.api.deps import get_analysis_service
from src.app.services.analysis_service import AnalysisService
from src.app.infra.mq import enqueue_analysis_job
from src.app.domain.value_objects import AnalysisScope, DateRange


router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/jobs", response_model=AnalysisJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: CreateAnalysisJobRequest,
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: AnalysisService = Depends(get_analysis_service),
):
    scope = AnalysisScope(
        source_ids=list(req.scope.source_ids),
        date_range=DateRange(start=req.scope.date_range.start, end=req.scope.date_range.end),
        query=req.scope.query,
    )

    # Создаём job
    try:
        job = svc.create_job(
            account_id=ctx.account_id,
            scope=scope,
        )
        if not job:
            raise HTTPException(status_code=500, detail="Job not returned")

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Публикуем в очередь. Если publish упал проставляем ERROR.
    try:
        await enqueue_analysis_job({"job_id": job.id})
    except Exception as e:
        try:
            svc.uow.analysis.set_error(job.id, f"mq_publish_error: {e}")
            svc.uow.commit()
        except Exception:
            svc.uow.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job created, but failed to enqueue. Please retry.",
        )

    return job_to_response(job)


@router.get("/jobs", response_model=list[AnalysisJobResponse])
def list_jobs(
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: AnalysisService = Depends(get_analysis_service),
    limit: int = 50,
):
    jobs = svc.list_jobs(ctx.account_id, limit=limit)
    return [job_to_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
def get_job(
    job_id: int,
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: AnalysisService = Depends(get_analysis_service),
):
    j = svc.get_job(ctx.account_id, job_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_response(j)


@router.get("/jobs/{job_id}/overview", response_model=OverviewReportResponse)
def get_overview(
    job_id: int,
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: AnalysisService = Depends(get_analysis_service),
):
    rep = svc.get_overview(ctx.account_id, job_id)
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Overview not found (job not DONE or missing report)",
        )
    return rep