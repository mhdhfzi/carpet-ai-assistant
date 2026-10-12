import pytest

from app.core.config import Settings


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_api_keys_count_as_unset(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    monkeypatch.setenv("VOYAGE_API_KEY", value)

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is None
    assert settings.voyage_api_key is None


def test_api_key_is_kept_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-secret"
    assert "sk-secret" not in repr(settings)
