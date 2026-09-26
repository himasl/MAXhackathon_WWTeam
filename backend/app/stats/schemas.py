from datetime import datetime

from pydantic import BaseModel


class RouteStats(BaseModel):
    created: int
    active: int
    completed: int
    completion_rate: float


class StepStats(BaseModel):
    done: int
    done_from_chat: int
    reminders_sent: int
    done_after_reminder: int
    # «Информация устарела» and similar notes from users about steps.
    reported: int = 0


class GroupStats(BaseModel):
    code: str
    title: str
    routes: int
    completed: int


class StatsResponse(BaseModel):
    """Anonymous aggregates for the pilot. No per-user data is exposed."""

    generated_at: datetime
    users: int
    routes: RouteStats
    steps: StepStats
    registration_median_days: float | None
    by_scenario: list[GroupStats]
    by_university: list[GroupStats]
