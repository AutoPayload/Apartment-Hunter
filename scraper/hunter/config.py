"""Runtime settings, read from environment variables (and a .env file if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    typesafe_api_key: str = field(default_factory=lambda: os.getenv("TYPESAFE_API_KEY", ""))
    usd_crc_rate: float = field(default_factory=lambda: _float("USD_CRC_RATE", 505.0))
    dashboard_url: str = field(default_factory=lambda: os.getenv("DASHBOARD_URL", ""))
    # Minimum seconds between two requests to the same host.
    request_delay: float = field(default_factory=lambda: _float("REQUEST_DELAY_SECONDS", 4.0))
    # Consecutive empty runs before a site is reported as broken.
    health_empty_runs: int = field(default_factory=lambda: _int("HEALTH_EMPTY_RUNS", 3))
    # Below this confidence a Jev answer is treated as "unknown".
    jev_min_confidence: float = field(default_factory=lambda: _float("JEV_MIN_CONFIDENCE", 0.6))
    user_agent: str = field(
        default_factory=lambda: os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0 Safari/537.36 apartment-hunter/0.1 (personal use)",
        )
    )


def get_settings() -> Settings:
    return Settings()
