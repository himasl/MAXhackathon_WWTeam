import os
from collections.abc import AsyncIterator
from typing import cast

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/marshrut_test",
)
os.environ["APP_ENV"] = "test"
os.environ["DEV_AUTH_ENABLED"] = "true"
os.environ["DEV_MAX_USER_ID"] = "123456"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import models as _models
from app.core.database import Base, async_session, engine
from app.main import app as fastapi_app
from app.scenarios.models import (
    Rule,
    RuleOperator,
    Scenario,
    ScenarioStep,
    StepCategory,
)
from app.sources.models import Source, SourceType

_MODELS_LOADED = _models

PROFILE = {
    "age": 18,
    "region_code": "77",
    "education_type": "FULL_TIME",
    "housing_type": "DORMITORY",
    "has_registration": False,
    "has_clinic_attachment": False,
}


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest_asyncio.fixture
async def saved_profile(client: AsyncClient) -> dict[str, object]:
    response = await client.put("/api/v1/profile", json=PROFILE)
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


@pytest_asyncio.fixture
async def active_scenario() -> Scenario:
    source = Source(
        title="Демонстрационный источник",
        url="https://example.test/source",
        organization="Тестовая организация",
        source_type=SourceType.MOCK,
        region_code="77",
    )
    scenario = Scenario(
        code="student_relocation_v1",
        title="Переезд студента",
        description="Тестовый сценарий",
        version=1,
        is_active=True,
        steps=[
            ScenarioStep(
                code="adult_step",
                title="Шаг для совершеннолетнего",
                short_description="Краткое описание",
                full_description="Полное описание",
                position=10,
                category=StepCategory.OTHER,
                estimated_duration=15,
                is_required=True,
                rules=[Rule(field="age", operator=RuleOperator.GTE, value=18)],
                sources=[source],
            ),
            ScenarioStep(
                code="registration_step",
                title="Регистрация",
                short_description="Проверьте регистрацию",
                full_description="Подготовьте данные для регистрации",
                position=20,
                category=StepCategory.REGISTRATION,
                estimated_duration=30,
                is_required=True,
                rules=[
                    Rule(
                        field="has_registration",
                        operator=RuleOperator.EQ,
                        value=False,
                    )
                ],
            ),
            ScenarioStep(
                code="attached_clinic_step",
                title="Уже прикреплён",
                short_description="Не должен попасть в маршрут",
                full_description="Не должен попасть в маршрут",
                position=30,
                category=StepCategory.HEALTHCARE,
                estimated_duration=None,
                is_required=False,
                rules=[
                    Rule(
                        field="has_clinic_attachment",
                        operator=RuleOperator.EQ,
                        value=True,
                    )
                ],
            ),
        ],
    )
    async with async_session() as session:
        session.add(scenario)
        await session.commit()
    return scenario
