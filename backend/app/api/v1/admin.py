"""The team panel (SUPPORT_MAX_USER_IDS only): metrics, regional sources, users' reports."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.admin.schemas import AdminOverview, AdminReport, AdminSource, SourceUpdate
from app.admin.service import AdminService
from app.api.dependencies import AdminDependency, SessionDependency
from app.api.errors import ERROR_RESPONSES

router = APIRouter(prefix="/admin", tags=["admin"], responses=ERROR_RESPONSES)
SourceKind = Literal["mfc", "tfoms", "transport", "regional", "federal"]


@router.get("/overview", response_model=AdminOverview)
async def get_overview(_: AdminDependency, session: SessionDependency) -> AdminOverview:
    """Business metrics: audience, activity by day, funnel, segments, problem steps."""
    return await AdminService(session).overview()


@router.get("/sources", response_model=list[AdminSource])
async def list_sources(
    _: AdminDependency,
    session: SessionDependency,
    region_code: str | None = None,
    kind: SourceKind | None = None,
    stale: bool = False,
) -> list[AdminSource]:
    """Official sources, filtered by region, kind or «not checked for 90+ days»."""
    return await AdminService(session).sources(region_code, kind, stale)


@router.patch("/sources/{source_id}", response_model=AdminSource)
async def update_source(
    source_id: UUID, payload: SourceUpdate, admin: AdminDependency, session: SessionDependency
) -> AdminSource:
    """Fix a link or organisation and/or mark the source as checked today.

    The edit wins over the data files: the next deploy does not overwrite it."""
    return await AdminService(session).update_source(source_id, payload, admin.max_user_id)


@router.get("/reports", response_model=list[AdminReport])
async def list_reports(
    _: AdminDependency, session: SessionDependency, resolved: bool = False
) -> list[AdminReport]:
    """Users' notes that a step is outdated or does not fit, newest first."""
    return await AdminService(session).reports(resolved)


@router.post(
    "/reports/{report_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def resolve_report(
    report_id: UUID, _: AdminDependency, session: SessionDependency
) -> Response:
    await AdminService(session).set_resolved(report_id, True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reports/{report_id}/reopen",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def reopen_report(
    report_id: UUID, _: AdminDependency, session: SessionDependency
) -> Response:
    await AdminService(session).set_resolved(report_id, False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
