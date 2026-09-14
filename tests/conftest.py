import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai import ModelHTTPError, ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.main import create_app
from src.modules.draft import build_agent, get_agent, get_conversation_limits
from src.registry import get_registry, load_registry
from src.utils import Conversation, RateLimiter, get_rate_limiter


REAL_SCHEMA = Path(__file__).parent.parent / "src" / "licenses" / "_schema.json"
FIXTURE_ACTIVE_BODY = "# Fixture Active License\n\nFixture license body for FIXTURE-ACTIVE."

_LICENSE_TEMPLATE = """---
id: {id}
name: {name}
shortName: {short_name}
version: "1.0"
category: creative_commons
officialUrl: https://example.com/{id}
summary: A fixture license.
permissions: [share]
limitations: []
conditions: [attribution]
active: {active}
order: {order}
---

# {name}

Fixture license body for {id}.
"""


@pytest.fixture
def fixture_registry_dir(tmp_path: Path) -> Path:
    shutil.copy(REAL_SCHEMA, tmp_path / "_schema.json")
    (tmp_path / "active.md").write_text(
        _LICENSE_TEMPLATE.format(
            id="FIXTURE-ACTIVE",
            name="Fixture Active License",
            short_name="Fixture Active",
            active=True,
            order=10,
        )
    )
    (tmp_path / "inactive.md").write_text(
        _LICENSE_TEMPLATE.format(
            id="FIXTURE-INACTIVE",
            name="Fixture Inactive License",
            short_name="Fixture Inactive",
            active=False,
            order=20,
        )
    )
    return tmp_path


def build_test_app(fixture_registry_dir: Path) -> FastAPI:
    app = create_app()
    registry = load_registry(fixture_registry_dir)
    permissive_limiter = RateLimiter(per_minute=1_000_000)
    permissive_limits = Conversation(max_turns=1_000_000, max_message_chars=1_000_000)
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_rate_limiter] = lambda: permissive_limiter
    app.dependency_overrides[get_conversation_limits] = lambda: permissive_limits
    return app


@pytest.fixture
def app(fixture_registry_dir: Path) -> FastAPI:
    """
    A fresh app per test.
    """

    return build_test_app(fixture_registry_dir)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def stub_agent() -> Callable[[FastAPI, dict], None]:
    def _stub(app: FastAPI, payload: dict) -> None:
        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            tool_name = info.output_tools[0].name
            return ModelResponse(parts=[ToolCallPart(tool_name, payload)])

        app.dependency_overrides[get_agent] = lambda: build_agent(FunctionModel(respond))

    return _stub


@pytest.fixture
def failing_agent() -> Callable[[FastAPI], None]:
    """
    Stub the agent to fail as an upstream LLM provider would (a 500, a timeout,
    a dropped connection) rather than return structured output, so tests can
    assert on `run_draft_agent`'s own fallback handling instead of on anything
    an LLM actually said.
    """

    def _stub(app: FastAPI) -> None:
        def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            raise ModelHTTPError(status_code=500, model_name="stub", body="upstream error")

        app.dependency_overrides[get_agent] = lambda: build_agent(FunctionModel(respond))

    return _stub
