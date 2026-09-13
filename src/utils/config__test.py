from pathlib import Path

from src.utils.config import Settings


def test_settings_defaults_apply_when_absent(monkeypatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("REGISTRY__PATH", raising=False)

    settings = Settings()  # act

    assert settings.port == 8000
    assert settings.registry.path == Path("./src/licenses")


def test_settings_reads_nested_registry_path_env_var(monkeypatch) -> None:
    monkeypatch.setenv("REGISTRY__PATH", "/tmp/licenses-fixture")

    settings = Settings()  # act

    assert settings.registry.path == Path("/tmp/licenses-fixture")


def test_settings_reads_flat_port_env_var(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "9000")

    settings = Settings()  # act

    assert settings.port == 9000
