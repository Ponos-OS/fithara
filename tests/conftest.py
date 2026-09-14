import os
import shutil
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import docker
import docker.errors
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from testcontainers.community.ollama import OllamaContainer
from testcontainers.core.image import DockerImage

from src.main import create_app
from src.modules.draft import build_agent, get_agent, get_conversation_limits
from src.registry import get_registry, load_registry
from src.utils import Conversation, RateLimiter, get_rate_limiter, get_settings


# Tests hit a real local Ollama server.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_MODEL = "llama3.2:1b"
OLLAMA_IMAGE = "fithara-ollama:latest"
OLLAMA_CONTEXT = PROJECT_ROOT / "local-setup" / "ollama"

REAL_SCHEMA = Path(__file__).parent.parent / "src" / "licenses" / "_schema.json"
FIXTURE_ACTIVE_BODY = "# Fixture Active License\n\nFixture license body for FIXTURE-ACTIVE."

# Mirrors src.modules.draft.agent's private `_FALLBACK_RESPONSE.assistant_message` — that
# module is a protected barrel internal (see pyproject.toml's import-linter contracts), so
# it can't be imported here. `run_draft_agent` returns this verbatim whenever the agent
# call fails (including a connection failure to Ollama), so a real-model test asserting
# the response isn't this sentinel is actually asserting "a real LLM call happened".
FALLBACK_ASSISTANT_MESSAGE = (
    "Sorry, I wasn't able to produce a reliable answer for that. "
    "Please try rephrasing your request."
)

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


def _ensure_ollama_image_exists() -> None:
    client = docker.from_env()

    try:
        client.images.get(OLLAMA_IMAGE)
        return
    except docker.errors.ImageNotFound:
        pass

    image = DockerImage(
        path=str(OLLAMA_CONTEXT),
        tag=OLLAMA_IMAGE,
        buildargs={"OLLAMA_MODEL": OLLAMA_MODEL},
    )
    image.build()


@pytest.fixture(scope="session")
def ollama_container() -> Iterator[OllamaContainer]:
    _ensure_ollama_image_exists()

    with OllamaContainer(image=OLLAMA_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def ollama_base_url(ollama_container: OllamaContainer) -> str:
    return f"{ollama_container.get_endpoint()}/v1"


@pytest.fixture(scope="session")
def ollama_env(ollama_base_url: str) -> None:
    os.environ["LLM__PROVIDER"] = "ollama"
    os.environ["LLM__MODEL"] = OLLAMA_MODEL
    os.environ["LLM__BASE_URL"] = ollama_base_url
    os.environ["LLM__API_KEY"] = "unused-local-ollama"
    get_settings.cache_clear()
