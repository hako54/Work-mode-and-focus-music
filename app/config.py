"""Ortam değişkenlerinden okunan sabit ayarlar.

Çalışma anında Telegram'dan değiştirilebilen ayarlar (yayın saati, süreler vb.)
`app.db` içindeki `settings` tablosunda tutulur; varsayılanları `app.profiles` içindedir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "evet"}


def _env_ids(name: str) -> set[int]:
    return {int(x) for x in _env(name).replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Config:
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    admin_ids: set[int] = field(default_factory=lambda: _env_ids("TELEGRAM_ADMIN_IDS"))

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-opus-5-5"))

    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    elevenlabs_model: str = field(default_factory=lambda: _env("ELEVENLABS_MUSIC_MODEL", "music_v1"))

    stability_api_key: str = field(default_factory=lambda: _env("STABILITY_API_KEY"))

    youtube_client_id: str = field(default_factory=lambda: _env("YOUTUBE_CLIENT_ID"))
    youtube_client_secret: str = field(default_factory=lambda: _env("YOUTUBE_CLIENT_SECRET"))
    youtube_refresh_token: str = field(default_factory=lambda: _env("YOUTUBE_REFRESH_TOKEN"))

    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "/data")))
    timezone: str = field(default_factory=lambda: _env("TIMEZONE", "Europe/Istanbul"))
    content_language: str = field(default_factory=lambda: _env("CONTENT_LANGUAGE", "en"))
    # Boşsa profilin varsayılan kanal adı kullanılır (bkz. app.profiles.channel_name).
    channel_name: str = field(default_factory=lambda: _env("CHANNEL_NAME"))
    # focus | romantic — bkz. app/profiles.py
    channel_profile: str = field(default_factory=lambda: _env("CHANNEL_PROFILE", "focus").lower())

    # true iken YouTube'a hiçbir şey yüklenmez; uçtan uca deneme için.
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "app.log"


# Profil bazlı varsayılan ayarlar ve açıklamaları `app.profiles` içindedir.

CONFIG = Config()
