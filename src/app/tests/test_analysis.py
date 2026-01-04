import pytest
from datetime import datetime, timezone, timedelta


@pytest.mark.anyio
async def test_create_job_rejects_empty_scope(client, seed_source_and_docs, auth_headers):
    token, source_id, _, _ = seed_source_and_docs

    end = datetime.now(timezone.utc).isoformat()
    start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    r = await client.post(
        "/api/analysis/jobs",
        headers=auth_headers(token),
        json={
            "model": {"name": "rubert-tiny2", "version": "v1"},
            "scope": {
                "source_ids": [],
                "date_range": {"start": start, "end": end},
                "query": None,
            },
            "params": {},
        },
    )
    assert r.status_code in (400, 422), r.text


@pytest.mark.anyio
async def test_create_job_rejects_no_docs_in_range(client, seed_source_and_docs, auth_headers):
    token, source_id, _, _ = seed_source_and_docs

    start = (datetime.now(timezone.utc) - timedelta(days=3650)).isoformat()
    end = (datetime.now(timezone.utc) - timedelta(days=3600)).isoformat()

    r = await client.post(
        "/api/analysis/jobs",
        headers=auth_headers(token),
        json={
            "model": {"name": "rubert-tiny2", "version": "v1"},
            "scope": {
                "source_ids": [source_id],
                "date_range": {"start": start, "end": end},
                "query": None,
            },
            "params": {},
        },
    )
    assert r.status_code == 400, r.text
    assert ("документ" in r.text.lower()) or ("не найден" in r.text.lower()), r.text


@pytest.mark.anyio
async def test_job_happy_path_run_and_overview(client, seed_source_and_docs, auth_headers, db_session, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    # ВАЖНО: патчим в модуле роутера, а не в infra.mq
    monkeypatch.setattr("src.app.api.routers.analysis.enqueue_analysis_job", _noop)

    token, source_id, _, seed_now = seed_source_and_docs
    start = (seed_now - timedelta(days=10)).isoformat()
    end = (seed_now + timedelta(days=1)).isoformat()

    r = await client.post(
        "/api/analysis/jobs",
        headers=auth_headers(token),
        json={
            "model": {"name": "rubert-tiny2", "version": "v1"},
            "scope": {"source_ids": [source_id], "date_range": {"start": start, "end": end}, "query": None},
            "params": {},
        },
    )
    assert r.status_code in (200, 201), r.text
    job_id = int(r.json()["id"])

    from src.app.infra.uow import SqlAlchemyUoW
    from src.app.services.analysis_service import AnalysisService

    uow = SqlAlchemyUoW(db_session)
    svc = AnalysisService(uow)
    svc.run_job(job_id)
    uow.commit()

    r2 = await client.get(f"/api/analysis/jobs/{job_id}", headers=auth_headers(token))
    assert r2.status_code == 200, r2.text
    job2 = r2.json()
    assert job2["status"] in ("DONE", "ERROR"), job2

    if job2["status"] == "DONE":
        r3 = await client.get(f"/api/analysis/jobs/{job_id}/overview", headers=auth_headers(token))
        assert r3.status_code == 200, r3.text
        rep = r3.json()
        assert "total_documents" in rep
        assert rep["total_documents"] >= 0