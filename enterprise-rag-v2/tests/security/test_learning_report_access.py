from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import (
    Base,
    LearningDiagnosisReport,
    LearningPracticeSession,
    Tenant,
    User,
)
from services.impl.learning_diagnosis_service import LearningDiagnosisServiceImpl


@pytest.fixture
async def learning_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _identity(session: AsyncSession, name: str) -> User:
    tenant = Tenant(name=f"{name}-tenant", contact_email=f"{uuid4()}@example.com")
    user = User(
        tenant=tenant, username=f"{name}-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash"
    )
    session.add_all([tenant, user])
    await session.flush()
    return user


async def _report(session: AsyncSession, user: User) -> LearningDiagnosisReport:
    report = LearningDiagnosisReport(
        id=str(uuid4()),
        user_id=str(user.id),
        subject_id=str(uuid4()),
        question_text="已知 2x + 1 = 5，求 x。",
    )
    session.add(report)
    await session.flush()
    return report


@pytest.mark.asyncio
async def test_get_report_rejects_non_owner(learning_session):
    owner = await _identity(learning_session, "owner")
    intruder = await _identity(learning_session, "intruder")
    report = await _report(learning_session, owner)
    service = LearningDiagnosisServiceImpl(learning_session)

    assert await service.get_report(str(report.id), str(owner.id)) is not None
    assert await service.get_report(str(report.id), str(intruder.id)) is None


@pytest.mark.asyncio
async def test_submit_feedback_rejects_non_owner(learning_session):
    owner = await _identity(learning_session, "owner")
    intruder = await _identity(learning_session, "intruder")
    report = await _report(learning_session, owner)
    service = LearningDiagnosisServiceImpl(learning_session)

    assert await service.submit_feedback(str(report.id), "good", "有帮助", str(intruder.id)) is False
    assert await service.submit_feedback(str(report.id), "good", "有帮助", str(owner.id)) is True


@pytest.mark.asyncio
async def test_start_practice_rejects_foreign_report(learning_session):
    owner = await _identity(learning_session, "owner")
    intruder = await _identity(learning_session, "intruder")
    report = await _report(learning_session, owner)
    service = LearningDiagnosisServiceImpl(learning_session)

    assert await service.start_practice(str(report.id), str(intruder.id)) is None


@pytest.mark.asyncio
async def test_practice_session_rejects_non_owner(learning_session):
    owner = await _identity(learning_session, "owner")
    intruder = await _identity(learning_session, "intruder")
    report = await _report(learning_session, owner)
    practice = LearningPracticeSession(
        id=str(uuid4()),
        diagnosis_report_id=str(report.id),
        user_id=str(owner.id),
        exercises=[{"idx": 1, "question": "化简表达式", "answer": "x = 2，代入后等式成立。"}],
    )
    learning_session.add(practice)
    await learning_session.flush()
    service = LearningDiagnosisServiceImpl(learning_session)

    assert await service.get_practice_session(str(practice.id), str(owner.id)) is not None
    assert await service.get_practice_session(str(practice.id), str(intruder.id)) is None

    intruder_result = await service.submit_practice_answer(
        str(practice.id), 1, "我的作答内容，尝试越权提交", str(intruder.id)
    )
    assert intruder_result is None
    await learning_session.refresh(practice)
    assert practice.answers_submitted == []
