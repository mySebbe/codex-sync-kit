from codex_sync_kit.rules import classify


def test_safe_profile_selects_agents_and_sanitized_config() -> None:
    assert classify("AGENTS.md", "safe").allowed
    config = classify("config.toml", "safe")
    assert config.allowed
    assert config.risky


def test_auth_and_live_state_are_blocked_even_when_risky_enabled() -> None:
    assert not classify("auth.json", "full", include_risky=True).allowed
    assert not classify("logs_2.sqlite-wal", "full", include_risky=True).allowed
    assert not classify("credentials.json", "full", include_risky=True).allowed
    assert not classify("service_account.json", "full", include_risky=True).allowed
    assert not classify(".env.local", "full", include_risky=True).allowed
    assert not classify("certs/signing.p12", "full", include_risky=True).allowed
    assert not classify(".env", "full", include_risky=True).allowed
    assert not classify("token.txt", "full", include_risky=True).allowed
    assert not classify("secret.txt", "full", include_risky=True).allowed
    assert not classify("password.txt", "full", include_risky=True).allowed


def test_full_profile_requires_confirmation_for_risky_files() -> None:
    assert not classify("tools/outlook-mail/outlook_mail.py", "full").allowed
    assert classify("tools/outlook-mail/outlook_mail.py", "full", include_risky=True).allowed
