"""Startup validation, login throttling, seed toggle."""

import pytest


def test_production_rejects_default_secret(monkeypatch):
    from mediqueue.config import get_settings, reset_settings

    monkeypatch.setenv("MEDIQUEUE_ENV", "production")
    monkeypatch.delenv("MEDIQUEUE_SECRET_KEY", raising=False)
    reset_settings()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings().validate_for_startup()
    reset_settings()


def test_production_rejects_wildcard_cors(monkeypatch):
    from mediqueue.config import get_settings, reset_settings

    monkeypatch.setenv("MEDIQUEUE_ENV", "production")
    monkeypatch.setenv("MEDIQUEUE_SECRET_KEY", "x" * 40)
    reset_settings()
    with pytest.raises(RuntimeError, match="CORS"):
        get_settings().validate_for_startup()
    monkeypatch.setenv("MEDIQUEUE_CORS_ORIGINS", "https://a.example")
    reset_settings()
    get_settings().validate_for_startup()
    assert get_settings().seed_users is False
    reset_settings()


def test_login_throttled_after_repeated_failures(client):
    from mediqueue.security import reset_login_throttle

    reset_login_throttle()
    bad = {"username": "clinician1", "password": "nope"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    r = client.post("/api/auth/login", json=bad)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # correct password is also blocked while throttled
    good = {"username": "clinician1", "password": "clinician1-pass"}
    assert client.post("/api/auth/login", json=good).status_code == 429
    reset_login_throttle()
    assert client.post("/api/auth/login", json=good).status_code == 200


def test_logout_revokes_token(client, token):
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    # logout twice is rejected (token no longer valid), never an error 500
    assert client.post("/api/auth/logout", headers=h).status_code == 401


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("MEDIQUEUE_BAND_WATCH", "0.8", "Risk-band thresholds"),
        ("MEDIQUEUE_ALERT_THRESHOLD", "1.1", "MEDIQUEUE_ALERT_THRESHOLD"),
        ("MEDIQUEUE_MATERIAL_WORSENING_DELTA", "0", "MEDIQUEUE_MATERIAL_WORSENING_DELTA"),
        ("MEDIQUEUE_ALERT_COOLDOWN_MINUTES", "nan", "MEDIQUEUE_ALERT_COOLDOWN_MINUTES"),
    ],
)
def test_invalid_thresholds_rejected_in_development(monkeypatch, variable, value, message):
    from mediqueue.config import get_settings, reset_settings

    monkeypatch.setenv("MEDIQUEUE_ENV", "dev")
    monkeypatch.setenv(variable, value)
    reset_settings()
    try:
        with pytest.raises(RuntimeError, match=message):
            get_settings().validate_for_startup()
    finally:
        reset_settings()


def test_valid_experimental_thresholds_are_accepted(monkeypatch):
    from mediqueue.config import get_settings, reset_settings

    monkeypatch.setenv("MEDIQUEUE_ENV", "dev")
    monkeypatch.setenv("MEDIQUEUE_BAND_WATCH", "0.17")
    monkeypatch.setenv("MEDIQUEUE_BAND_ELEVATED", "0.30")
    monkeypatch.setenv("MEDIQUEUE_BAND_HIGH", "0.50")
    monkeypatch.setenv("MEDIQUEUE_ALERT_THRESHOLD", "0.17")
    reset_settings()
    try:
        settings = get_settings()
        settings.validate_for_startup()
        assert settings.band_watch == 0.17
        assert settings.alert_absolute_threshold == 0.17
    finally:
        reset_settings()
