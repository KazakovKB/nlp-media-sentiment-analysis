from fastapi import APIRouter, Depends, HTTPException, status

from src.app.api.deps import UserContext, get_current_user_ctx
from src.app.api.schemas import SourceResponse, SourceStatsResponse
from src.app.api.deps import get_sources_service
from src.app.services.sources_service import SourcesService


router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
def list_sources(
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: SourcesService = Depends(get_sources_service),
):
    return svc.list_sources(ctx.account_id)


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(
    source_id: int,
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: SourcesService = Depends(get_sources_service),
):
    s = svc.get_source(ctx.account_id, source_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return s


@router.get("/{source_id}/stats", response_model=SourceStatsResponse)
def source_stats(
    source_id: int,
    ctx: UserContext = Depends(get_current_user_ctx),
    svc: SourcesService = Depends(get_sources_service),
):
    st = svc.source_stats(ctx.account_id, source_id)
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceStatsResponse(**st)