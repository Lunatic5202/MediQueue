"""Runtime configuration.

All thresholds and clinical display parameters are configurable experimental
values; they are not clinically validated defaults. Environment variables use
the MEDIQUEUE_ prefix.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEV_SECRET = "dev-only-insecure-secret"


@dataclass
class Settings:
    # --- Environment: "dev" (default) or "production" ---
    env: str = field(default_factory=lambda: _env_str("MEDIQUEUE_ENV", "dev").lower())

    # --- Persistence ---
    database_url: str = field(
        default_factory=lambda: _env_str(
            "MEDIQUEUE_DATABASE_URL",
            "sqlite:///backend/mediqueue/data/mediqueue.db",
        )
    )

    # --- History / windows ---
    history_window_hours: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_HISTORY_WINDOW_HOURS", 4.0)
    )
    max_history_per_patient: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_MAX_HISTORY_PER_PATIENT", 2000)
    )
    short_horizon_minutes: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_SHORT_HORIZON_MINUTES", 15.0)
    )

    # --- Low-history rule ---
    min_readings_for_confidence: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_MIN_READINGS", 3)
    )
    min_span_minutes_for_confidence: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_MIN_SPAN_MINUTES", 10.0)
    )

    # --- Risk bands (display categories only; thresholds are experimental) ---
    band_watch: float = field(default_factory=lambda: _env_float("MEDIQUEUE_BAND_WATCH", 0.30))
    band_elevated: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_BAND_ELEVATED", 0.50)
    )
    band_high: float = field(default_factory=lambda: _env_float("MEDIQUEUE_BAND_HIGH", 0.75))

    # --- Alerting ---
    alert_absolute_threshold: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_ALERT_THRESHOLD", 0.60)
    )
    alert_cooldown_minutes: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_ALERT_COOLDOWN_MINUTES", 15.0)
    )
    trend_min_readings: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_TREND_MIN_READINGS", 3)
    )
    trend_min_span_minutes: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_TREND_MIN_SPAN_MINUTES", 20.0)
    )
    material_worsening_delta: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_MATERIAL_WORSENING_DELTA", 0.15)
    )

    # --- Queue recommendations ---
    max_priority_step: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_MAX_PRIORITY_STEP", 1)
    )
    min_band_for_recommendation: str = field(
        default_factory=lambda: _env_str("MEDIQUEUE_MIN_BAND_FOR_RECOMMENDATION", "elevated")
    )

    # --- Simulator ---
    simulator_default_patients: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_SIM_PATIENTS", 20)
    )
    simulator_default_rate_per_min: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_SIM_RATE_PER_MIN", 30.0)
    )

    # --- Security ---
    secret_key: str = field(
        default_factory=lambda: _env_str("MEDIQUEUE_SECRET_KEY", DEV_SECRET)
    )
    # Demo accounts: on by default in dev, off in production unless opted in.
    seed_users: bool = field(
        default_factory=lambda: _env_bool(
            "MEDIQUEUE_SEED_USERS", _env_str("MEDIQUEUE_ENV", "dev").lower() != "production"
        )
    )
    # Comma-separated origins; "*" only allowed in dev.
    cors_origins: str = field(default_factory=lambda: _env_str("MEDIQUEUE_CORS_ORIGINS", "*"))
    # Login throttling (per client IP + username, in-memory).
    login_max_attempts: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_LOGIN_MAX_ATTEMPTS", 5)
    )
    login_window_seconds: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_LOGIN_WINDOW_SECONDS", 300)
    )
    token_ttl_seconds: int = field(
        default_factory=lambda: _env_int("MEDIQUEUE_TOKEN_TTL_SECONDS", 8 * 3600)
    )

    # --- Model ---
    model_version: str = field(default_factory=lambda: _env_str("MEDIQUEUE_MODEL_VERSION", ""))
    artifacts_dir: str = field(
        default_factory=lambda: _env_str("MEDIQUEUE_ARTIFACTS_DIR", "artifacts/models")
    )

    # --- Prediction horizon for the general-deterioration task (minutes) ---
    deterioration_horizon_minutes: float = field(
        default_factory=lambda: _env_float("MEDIQUEUE_DETERIORATION_HORIZON_MINUTES", 30.0)
    )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_for_startup(self) -> None:
        """Validate experimental thresholds in every environment and production secrets."""
        probability_thresholds = {
            "MEDIQUEUE_BAND_WATCH": self.band_watch,
            "MEDIQUEUE_BAND_ELEVATED": self.band_elevated,
            "MEDIQUEUE_BAND_HIGH": self.band_high,
            "MEDIQUEUE_ALERT_THRESHOLD": self.alert_absolute_threshold,
        }
        for name, value in probability_thresholds.items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise RuntimeError(f"{name} must be a finite probability between 0 and 1")

        if not self.band_watch < self.band_elevated < self.band_high:
            raise RuntimeError(
                "Risk-band thresholds must be strictly increasing: "
                "MEDIQUEUE_BAND_WATCH < MEDIQUEUE_BAND_ELEVATED < MEDIQUEUE_BAND_HIGH"
            )

        if (
            not math.isfinite(self.material_worsening_delta)
            or not 0.0 < self.material_worsening_delta <= 1.0
        ):
            raise RuntimeError(
                "MEDIQUEUE_MATERIAL_WORSENING_DELTA must be greater than 0 and at most 1"
            )

        if not math.isfinite(self.alert_cooldown_minutes) or self.alert_cooldown_minutes < 0.0:
            raise RuntimeError("MEDIQUEUE_ALERT_COOLDOWN_MINUTES must be finite and non-negative")

        if not self.is_production:
            return
        if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
            raise RuntimeError(
                "MEDIQUEUE_SECRET_KEY must be set to a random value of 32+ characters "
                "when MEDIQUEUE_ENV=production"
            )
        if "*" in self.cors_origin_list():
            raise RuntimeError(
                "MEDIQUEUE_CORS_ORIGINS must list explicit origins when "
                "MEDIQUEUE_ENV=production"
            )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Re-read environment; used by tests."""
    global _settings
    _settings = None
