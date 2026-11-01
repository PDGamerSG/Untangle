from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from untangle.answer import service as answers
from untangle.repositories import jobs, service

router = APIRouter()


class ImportRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=250)


@router.get("/repository-imports")
def imports():
    return service.status(answers.get_graph())


@router.post("/repository-imports", status_code=202)
def add_repository(body: ImportRequest):
    # Validate before touching the database, even when the database is unavailable.
    service.normalize_repository(body.repository)
    return service.submit(body.repository, answers.get_graph())


@router.get("/repository-imports/{job_id}")
def import_status(job_id: str):
    graph = answers.get_graph()
    jobs.expire_stalled(graph)
    return jobs.get_job(graph, job_id)


@router.get("/repository-overview")
def repository_overview(repo: str = Query(min_length=3, max_length=150)):
    return service.overview(repo, answers.get_graph())
