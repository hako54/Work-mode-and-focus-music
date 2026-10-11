"""Müzik üretimi: ElevenLabs Music API (ticari kullanım lisanslı, resmi API).

Başka bir sağlayıcıya geçmek için `MusicProvider` arayüzüne uyan bir sınıf
yazıp `get_provider()` içinde döndürmek yeterli.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Protocol

import requests

from .config import CONFIG

log = logging.getLogger(__name__)


class MusicProvider(Protocol):
    def compose(self, prompt: str, duration_sec: int, out_path: Path) -> Path: ...


class MusicError(RuntimeError):
    pass


class ElevenLabsMusic:
    URL = "https://api.elevenlabs.io/v1/music"
    MAX_MS = 600_000

    def __init__(self, api_key: str, model_id: str):
        if not api_key:
            raise MusicError("ELEVENLABS_API_KEY tanımlı değil")
        self.api_key = api_key
        self.model_id = model_id

    def compose(self, prompt: str, duration_sec: int, out_path: Path) -> Path:
        body = {
            "prompt": prompt,
            "music_length_ms": max(10_000, min(self.MAX_MS, duration_sec * 1000)),
            "model_id": self.model_id,
            "force_instrumental": True,
        }
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    self.URL,
                    params={"output_format": "mp3_44100_192"},
                    headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                    json=body,
                    timeout=900,
                )
                if resp.status_code == 200 and resp.content:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(resp.content)
                    return out_path
                # 4xx (429 hariç) tekrar denenmez: kota/prompt hatası
                msg = f"ElevenLabs {resp.status_code}: {resp.text[:300]}"
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise MusicError(msg)
                last_err = MusicError(msg)
            except requests.RequestException as e:
                last_err = e
            wait = 15 * (attempt + 1)
            log.warning("Müzik üretimi başarısız (%s), %ss sonra tekrar", last_err, wait)
            time.sleep(wait)
        raise MusicError(f"Müzik üretilemedi: {last_err}")


def get_provider() -> MusicProvider:
    return ElevenLabsMusic(CONFIG.elevenlabs_api_key, CONFIG.elevenlabs_model)
