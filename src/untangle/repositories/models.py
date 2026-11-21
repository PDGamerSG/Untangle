from __future__ import annotations

LIMITS = {"max_repository_size_kb": 100_000, "max_commits": 1000, "max_prs": 50, "max_issues": 100, "imports_per_day": 20}
MAX_PENDING = 6
REFRESH_INTERVAL_MS = 60 * 60 * 1000
LEASE_TIMEOUT_MS = 3 * 60 * 1000
# A full queue must survive the preceding jobs' workflow budgets and scheduling.
QUEUE_TIMEOUT_MS = MAX_PENDING * 50 * 60 * 1000


class ImportProblem(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)
