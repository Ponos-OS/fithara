from pydantic_ai.models.openai import OpenAIChatModel

from src.modules.draft.model import build_model
from src.utils import Llm, LlmProvider


def test_openai_compatible_builds_an_openai_model_against_the_base_url() -> None:
    llm = Llm(
        provider=LlmProvider.OPENAI_COMPATIBLE,
        model="local-model",
        api_key="sk-test",
        base_url="http://localhost:8080/v1",
    )

    result = build_model(llm)

    assert isinstance(result, OpenAIChatModel)
    assert result.model_name == "local-model"
    assert str(result.client.base_url).startswith("http://localhost:8080/v1")
