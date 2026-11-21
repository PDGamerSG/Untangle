from __future__ import annotations

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from untangle.answer import service as answers
from untangle.api.auth import CurrentUser
from untangle.repositories import jobs, mine, service
from untangle.repositories.models import ImportProblem

router = APIRouter()


class ImportRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=250)


@router.get("/repository-imports")
def imports():
    return service.status(answers.get_graph())


@router.post("/repository-imports", status_code=202)
def add_repository(body: ImportRequest, user: CurrentUser):
    # Validate before touching the database, even when the database is unavailable.
    service.normalize_repository(body.repository)
    job = service.submit(body.repository, answers.get_graph())
    # The person who adds a repository keeps it in their own list. A full list must not block the import itself.
    try:
        mine.save(answers.get_graph(), user, job.get("repo") or body.repository)
    except ImportProblem:
        pass
    return job


@router.get("/repository-imports/{job_id}")
def import_status(job_id: str):
    graph = answers.get_graph()
    jobs.expire_stalled(graph)
    return jobs.get_job(graph, job_id)


@router.get("/repository-overview")
def repository_overview(repo: str = Query(min_length=3, max_length=150)):
    return service.overview(repo, answers.get_graph())


@router.get("/github/repositories")
def github_repositories(user: CurrentUser, owner: str | None = Query(default=None, max_length=100)):
    return mine.github_repositories(answers.get_graph(), user, owner)


@router.get("/my/repositories")
def my_repositories(user: CurrentUser):
    return mine.saved_repositories(answers.get_graph(), user)


@router.post("/my/repositories", status_code=201)
def save_repository(body: ImportRequest, user: CurrentUser):
    return mine.save(answers.get_graph(), user, body.repository)


@router.delete("/my/repositories", status_code=204)
def remove_repository(user: CurrentUser, repo: str = Query(min_length=3, max_length=150)):
    mine.unsave(answers.get_graph(), user, repo)
    return Response(status_code=204)


@router.get("/my/repositories/changes")
def repository_changes(user: CurrentUser, repo: str = Query(min_length=3, max_length=150)):
    return mine.changes(answers.get_graph(), user, repo)
