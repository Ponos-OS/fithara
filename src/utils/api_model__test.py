from src.utils import CamelModel


class _Example(CamelModel):
    name: str


def test_camel_model_strips_leading_and_trailing_whitespace() -> None:
    example = _Example(name="  hello  ")  # act

    assert example.name == "hello"


def test_camel_model_does_not_strip_internal_whitespace() -> None:
    example = _Example(name="  hello   world  ")  # act

    assert example.name == "hello   world"
