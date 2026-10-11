"""Ortam değişkenlerinden okunan sabit ayarlar.

Çalışma anında Telegram'dan değiştirilebilen ayarlar (yayın saati, süreler vb.)
`app.db` içindeki `settings` tablosunda tutulur; buradaki değerler varsayılandır.
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
    channel_name: str = field(default_factory=lambda: _env("CHANNEL_NAME", "Work Mode & Focus Music"))

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


# Telegram'dan /ayar ile değiştirilebilen ayarlar ve varsayılanları.
DEFAULT_SETTINGS: dict[str, str] = {
    "generate_time": "09:00",        # günlük üretim + onaya gönderme (yerel saat)
    "publish_time": "17:00",         # yayın saati (yerel saat; İstanbul 17:00 = ABD doğu 10:00)
    "daily_min_sec": "180",
    "daily_max_sec": "300",
    "compilation_every_days": "15",
    "compilation_min_min": "30",
    "compilation_max_min": "60",
    "make_shorts": "1",
    "short_seconds": "45",
    "short_delay_hours": "5",        # Short, ana videodan kaç saat sonra yayınlansın
    "reminder_hours": "4",           # onay bekleyen için hatırlatma aralığı
    "auto_approve_hours": "0",       # 0 = kapalı; >0 ise bu kadar saat cevap yoksa otomatik onay
    "paused": "0",
}

SETTING_HELP: dict[str, str] = {
    "generate_time": "Günlük üretim saati (SS:DD)",
    "publish_time": "Yayın saati (SS:DD)",
    "daily_min_sec": "Günlük parça en kısa süre (sn)",
    "daily_max_sec": "Günlük parça en uzun süre (sn)",
    "compilation_every_days": "Derleme sıklığı (gün)",
    "compilation_min_min": "Derleme en kısa süre (dk)",
    "compilation_max_min": "Derleme en uzun süre (dk)",
    "make_shorts": "Her parçadan Short üret (1/0)",
    "short_seconds": "Short uzunluğu (sn, en fazla 60)",
    "short_delay_hours": "Short yayın gecikmesi (saat)",
    "reminder_hours": "Onay hatırlatma aralığı (saat)",
    "auto_approve_hours": "Cevapsız kalırsa otomatik onay (saat, 0=kapalı)",
    "paused": "Otomasyon duraklatıldı mı (1/0)",
}

CONFIG = Config()
