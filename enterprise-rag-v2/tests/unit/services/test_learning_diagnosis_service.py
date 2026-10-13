import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import core.rag.llm_provider as llm_provider_module
import services.impl.learning_diagnosis_service as ld_module
from infrastructure.database.models import (
    Base,
    LearningDiagnosisReport,
    LearningErrorRecord,
    LearningKnowledgePoint,
    LearningMaterial,
    LearningSubject,
)
from services.impl.learning_diagnosis_service import LearningDiagnosisServiceImpl
from services.interfaces.learning_diagnosis_service import LearningDiagnosisContext


@pytest.fixture
async def diagnosis_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


class FakeHTTPResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


class _FakeStreamContext:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return SimpleNamespace(status_code=200, aiter_lines=self._aiter_lines, aread=self._aread)

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def _aiter_lines(self):
        for line in self._lines:
            yield line

    async def _aread(self):
        return b"error"


class FakeLLMClient:
    def __init__(self, calls, *, post_result=None, post_error=None, stream_lines=None):
        self._calls = calls
        self._post_result = post_result
        self._post_error = post_error
        self._stream_lines = stream_lines or []

    async def post(self, url, json=None):
        self._calls.append({"url": url, "payload": json})
        if self._post_error is not None:
            raise self._post_error
        return self._post_result

    def stream(self, method, url, json=None):
        self._calls.append({"url": url, "payload": json})
        return _FakeStreamContext(self._stream_lines)


def _patch_llm(monkeypatch, calls, *, post_result=None, post_error=None, stream_lines=None):
    class FakeProvider:
        def __init__(self, api_key=None, model=None, base_url=None):
            self.api_key = api_key
            self.model_name = model
            self.base_url = "https://fake-llm.test"

        async def _get_client(self):
            return FakeLLMClient(calls, post_result=post_result, post_error=post_error, stream_lines=stream_lines)

        async def close(self):
            pass

    async def fake_runtime(session, user_id):
        return {"provider": "deepseek", "api_key": "sk-test", "base_url": "https://fake-llm.test", "model": "deepseek-chat"}

    monkeypatch.setattr(ld_module, "resolve_user_llm_runtime", fake_runtime)
    monkeypatch.setattr(llm_provider_module, "DeepSeekProvider", FakeProvider)


async def _seed_world(session):
    subject = LearningSubject(name="数学", grade_level="junior_high")
    session.add(subject)
    await session.flush()
    kp = LearningKnowledgePoint(
        subject_id=str(subject.id), name="一元一次方程", code="M8-C3-KP01",
        chapter="第三章", difficulty_level=3,
    )
    session.add(kp)
    await session.flush()
    material = LearningMaterial(
        knowledge_point_id=str(kp.id), content_type="textbook",
        title="七上第三章", content="一元一次方程：移项要变号，系数化为一。", page_number=88,
    )
    error = LearningErrorRecord(
        knowledge_point_id=str(kp.id), error_type="概念不清",
        error_description="认为移项不需要变号", frequency=3,
    )
    session.add_all([material, error])
    await session.flush()
    return subject, kp


def _context(subject, **overrides):
    values = dict(
        question_text="解方程 2x+3=7 时移项忘记变号",
        kp_code="M8-C3-KP01",
        subject_info="初中数学",
        subject_id=str(subject.id),
        grade_level="junior_high",
        error_tags=["计算错误"],
        user_id="user-1",
        original_answer="2x=7+3 → x=5",
    )
    values.update(overrides)
    return LearningDiagnosisContext(**values)


@pytest.mark.asyncio
async def test_stage1_no_match_returns_empty(diagnosis_session):
    subject, _kp = await _seed_world(diagnosis_session)
    service = LearningDiagnosisServiceImpl(diagnosis_session)

    result = await service._stage1_knowledge_point_match(_context(subject, kp_code=None, question_text="与数学无关的描述"))

    assert result.status == "done"
    assert result.data["matched"] is False
    assert result.data["count"] == 0
    assert result.data["knowledge_points"] == []


@pytest.mark.asyncio
async def test_analyze_happy_path_saves_report(diagnosis_session, monkeypatch):
    subject, kp = await _seed_world(diagnosis_session)
    calls = []
    _patch_llm(
        monkeypatch, calls,
        post_result=FakeHTTPResponse(body={"choices": [{"message": {"content": "### 1. 错误定位\n移项未变号"}}]}),
    )
    service = LearningDiagnosisServiceImpl(diagnosis_session)

    result = await service.analyze(_context(subject))

    assert result["report_id"]
    stages = result["stage_results"]
    assert set(stages) == {"stage_1", "stage_2", "stage_3", "stage_4", "stage_5"}
    assert stages["stage_1"]["data"]["matched"] is True
    assert stages["stage_2"]["data"]["count"] >= 1
    assert stages["stage_3"]["data"]["matched"] is True
    assert stages["stage_4"]["status"] == "done"
    assert stages["stage_5"]["status"] == "done"

    assert calls[0]["url"] == "https://fake-llm.test/chat/completions"
    assert calls[0]["payload"]["messages"][0]["role"] == "system"

    report = (
        await diagnosis_session.execute(
            select(LearningDiagnosisReport).where(LearningDiagnosisReport.id == result["report_id"])
        )
    ).scalar_one()
    assert report.weak_knowledge_points[0]["name"] == "一元一次方程"
    assert report.report_content["report_text"].startswith("### 1. 错误定位")
    assert report.subject_id == str(subject.id)

    sediment = (
        (await diagnosis_session.execute(
            select(LearningErrorRecord).where(LearningErrorRecord.error_type == "计算错误")
        ))
        .scalars()
        .all()
    )
    assert len(sediment) == 1
    assert sediment[0].knowledge_point_id == str(kp.id)


@pytest.mark.asyncio
async def test_stage4_llm_exception_marks_error(diagnosis_session, monkeypatch):
    subject, _kp = await _seed_world(diagnosis_session)
    calls = []
    _patch_llm(monkeypatch, calls, post_error=RuntimeError("连接超时"))
    service = LearningDiagnosisServiceImpl(diagnosis_session)

    result = await service.analyze(_context(subject))

    assert result["stage_results"]["stage_4"]["status"] == "error"
    assert "连接超时" in result["stage_results"]["stage_4"]["data"]["error"]
    assert result["report_content"] is None
    assert result["report_id"]


@pytest.mark.asyncio
async def test_stage4_llm_http_error_uses_fallback(diagnosis_session, monkeypatch):
    subject, _kp = await _seed_world(diagnosis_session)
    calls = []
    _patch_llm(monkeypatch, calls, post_result=FakeHTTPResponse(status_code=503, text="upstream overloaded"))
    service = LearningDiagnosisServiceImpl(diagnosis_session)

    result = await service.analyze(_context(subject))

    s4 = result["stage_results"]["stage_4"]
    assert s4["status"] == "done"
    assert "HTTP 503" in s4["data"]["report_text"]
    assert result["report_content"]["report_text"] == s4["data"]["report_text"]


def _parse_sse(chunks):
    events = []
    for block in "".join(chunks).split("\n\n"):
        if not block.strip():
            continue
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        events.append((name, data))
    return events


@pytest.mark.asyncio
async def test_analyze_stream_event_sequence(diagnosis_session, monkeypatch):
    subject, _kp = await _seed_world(diagnosis_session)
    calls = []
    _patch_llm(
        monkeypatch, calls,
        stream_lines=[
            'data: {"choices": [{"delta": {"content": "### 1. 错误定位\\n"}}]}',
            'data: {"choices": [{"delta": {"content": "移项要变号。"}}]}',
            "data: [DONE]",
        ],
    )
    service = LearningDiagnosisServiceImpl(diagnosis_session)

    chunks = [event async for event in service.analyze_stream(_context(subject))]
    events = _parse_sse(chunks)

    assert events[0][0] == "stage" and events[0][1]["status"] == "running"
    assert events[-1][0] == "done"
    stage_flow = [(data["stage"], data["status"]) for name, data in events if name == "stage"]
    assert stage_flow == [
        (1, "running"), (1, "done"),
        (2, "running"), (2, "done"),
        (3, "running"), (3, "done"),
        (4, "running"),
        (5, "running"), (5, "done"),
    ]
    progress = [data["percent"] for name, data in events if name == "progress"]
    assert progress == [0.2, 0.5, 0.65, 0.95]

    contents = [data for name, data in events if name == "content"]
    assert "".join(item["text"] for item in contents) == "### 1. 错误定位\n移项要变号。"

    sources = [data for name, data in events if name == "sources"]
    assert sources and "系数化为一" in sources[0]["documents"][0]["content"]

    report_id = events[-1][1]["report_id"]
    assert report_id
    report = (
        await diagnosis_session.execute(
            select(LearningDiagnosisReport).where(LearningDiagnosisReport.id == report_id)
        )
    ).scalar_one()
    assert report.report_content["report_text"] == "### 1. 错误定位\n移项要变号。"
