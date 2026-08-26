import pytest
from config import validate_config


def test_validate_config_missing_token(monkeypatch):
    monkeypatch.setattr("config.DISCORD_BOT_TOKEN", "")
    monkeypatch.setattr("config.DISCORD_CHANNEL_ID", 123456)
    valid, msg = validate_config()
    assert valid is False
    assert "DISCORD_BOT_TOKEN" in msg


def test_validate_config_placeholder_token(monkeypatch):
    monkeypatch.setattr("config.DISCORD_BOT_TOKEN", "tu_token_de_discord_aqui")
    monkeypatch.setattr("config.DISCORD_CHANNEL_ID", 123456)
    valid, msg = validate_config()
    assert valid is False
    assert "DISCORD_BOT_TOKEN" in msg


def test_validate_config_missing_channel(monkeypatch):
    monkeypatch.setattr("config.DISCORD_BOT_TOKEN", "valid_token_123")
    monkeypatch.setattr("config.DISCORD_CHANNEL_ID", None)
    valid, msg = validate_config()
    assert valid is False
    assert "DISCORD_CHANNEL_ID" in msg


def test_validate_config_valid(monkeypatch):
    monkeypatch.setattr("config.DISCORD_BOT_TOKEN", "OTc1NDM5MjM5NDg1NzQzOTEy.Gz...")
    monkeypatch.setattr("config.DISCORD_CHANNEL_ID", 987654321012345678)
    valid, msg = validate_config()
    assert valid is True
