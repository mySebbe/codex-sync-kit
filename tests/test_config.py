import tomllib
from pathlib import Path

from codex_sync_kit.config import AppConfig, load_config, redact_config_text, save_config


def test_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    saved = save_config(
        AppConfig(owner="me", vault="vault", codex_home="C:/Users/me/.codex", vault_dir="D:/vault"),
        path,
    )

    loaded = load_config(saved)

    assert loaded.owner == "me"
    assert loaded.vault == "vault"
    assert loaded.codex_home == "C:/Users/me/.codex"
    assert loaded.resolved_vault_dir.as_posix() == "D:/vault"


def test_redact_config_text_keeps_non_secret_values() -> None:
    text = 'model = "gpt-5"\napi_key = "abc"\n[mcp.env]\nTOKEN = "def"\n'

    redacted = redact_config_text(text)

    assert 'model = "gpt-5"' in redacted
    assert 'api_key = "<redacted>"' in redacted
    assert 'TOKEN = "<redacted>"' in redacted
    assert "abc" not in redacted
    assert "def" not in redacted


def test_redact_config_text_redacts_inline_toml_secrets() -> None:
    text = (
        'model = "gpt-5"\n'
        'env = { OPENAI_API_KEY = "sk-test123", SAFE_VALUE = "kept" }\n'
        'headers = { Authorization = "Bearer abc123" }\n'
    )

    redacted = redact_config_text(text)

    assert "sk-test123" not in redacted
    assert "Bearer abc123" not in redacted
    assert "SAFE_VALUE" in redacted
    assert "kept" in redacted


def test_redact_config_text_keeps_path_keys_parseable() -> None:
    text = """
[projects.'c:\\users\\me\\wieviel-tokens-hab-ich']
trust_level = "trusted"

[plugins."github@openai-curated"]
enabled = true
"""

    redacted = redact_config_text(text)
    parsed = tomllib.loads(redacted)

    assert parsed["projects"]["c:\\users\\me\\wieviel-tokens-hab-ich"]["trust_level"] == "trusted"
    assert parsed["plugins"]["github@openai-curated"]["enabled"] is True
