"""Tests for application settings and URL/CORS normalization."""

from app.config import Settings


def test_settings_default_values():
    """Verify default settings initialization."""
    settings = Settings()
    assert settings.project_name == "Smart Child Monitoring and Safety System"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.port == 8000
    assert settings.location_stale_minutes == 15
    assert settings.pairing_code_expiry_minutes == 15


def test_postgres_url_normalization():
    """Verify postgres:// is rewritten to postgresql+psycopg://."""
    raw_render_url = "postgres://user:pass@ep-demo.neon.tech/child_safety"
    normalized = Settings.normalize_database_url(raw_render_url)
    assert normalized.startswith("postgresql+psycopg://")
    assert "user:pass@ep-demo.neon.tech/child_safety" in normalized


def test_cors_origins_parsing():
    """Verify JSON string and comma-separated string CORS origins are parsed to list."""
    json_origins = '["https://parent.app", "https://dashboard.app"]'
    parsed_json = Settings.parse_cors_origins(json_origins)
    assert parsed_json == ["https://parent.app", "https://dashboard.app"]

    csv_origins = "https://parent.app, https://dashboard.app"
    parsed_csv = Settings.parse_cors_origins(csv_origins)
    assert parsed_csv == ["https://parent.app", "https://dashboard.app"]
