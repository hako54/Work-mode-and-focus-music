"""Gerçek şömine sesi adayları: Freesound (CC0 kayıtlar) + Pexels şömine videolarının kendi sesi.

Her aday indirilir, "çıtırtı" ölçülür (saniyedeki belirgin odun çıtırtısı; ince çızırtı/hışırtı elenir),
sıcak tona getirilir ve dikişsiz döngü yapılır. /atessesi ara ile adaylar Telegram'a gönderilir, kulakla
seçilir; seçilmezse otomatik olarak en çıtırtılısı kullanılır.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

import requests

from . import fireplace, stock
from .config import CONFIG

log = logging.getLogger(__name__)

FREESOUND_URL = "https://freesound.org/apiv2/search/text/"
FREESOUND_QUERIES = ("fireplace crackling", "fireplace logs burning", "wood fire crackling close")
PEXELS_QUERIES = ("fireplace crackling", "fireplace burning logs", "fireplace close up fire", "burning firewood")
BAD_WORDS = ("grass", "leaves", "paper", "straw", "gas", "match", "torch", "candle", "rain", "explosion", "music",
             "voice", "talk", "song", "wind")
MAX_DOWNLOADS = 10
PICK_COUNT = 4
MIN_CHOICE_CRACKLES = 1.0   # kulakla seçimde biraz daha esnek; otomatikte fireplace.MIN_CRACKLES_PER_SEC


def pick_dir() -> Path:
    d = fireplace.cache_dir() / "fire_pick"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _bad(title: str) -> bool:
    t = title.lower()
    return any(w in t for w in BAD_WORDS)


def _freesound_sources() -> list[dict]:
    if not CONFIG.freesound_api_key:
        return []
    out: list[dict] = []
    for q in FREESOUND_QUERIES:
        try:
            r = requests.get(FREESOUND_URL, headers=fireplace.UA, timeout=30, params={
                "query": q, "filter": 'license:"Creative Commons 0" duration:[20 TO 900]',
                "fields": "id,name,previews,duration,username,avg_rating,num_downloads",
                "sort": "rating_desc", "page_size": 8, "token": CONFIG.freesound_api_key})
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("Freesound araması başarısız (%s): %s", q, e)
            continue
        for s in r.json().get("results", []):
            url = (s.get("previews") or {}).get("preview-hq-mp3")
            if url and not _bad(s.get("name", "")):
                out.append({"key": f"fs{s['id']}", "url": url, "ext": ".mp3", "source": "Freesound, CC0",
                            "title": f"{s.get('name', '')} — {s.get('username', '')}"})
    return out


def _smallest_file(files: list[dict]) -> dict | None:
    mp4 = [f for f in files if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 480]
    return min(mp4, key=lambda f: f.get("width") or 9999) if mp4 else None   # yalnızca ses lazım: en küçük dosya


def _pexels_sources() -> list[dict]:
    if not stock.available():
        return []
    out: list[dict] = []
    for q in PEXELS_QUERIES:
        try:
            res = stock._get("/videos/search", {"query": q, "per_page": 20, "size": "small"})
        except (requests.RequestException, ValueError) as e:
            log.warning("Pexels ses araması başarısız (%s): %s", q, e)
            continue
        for v in res.get("videos", []):
            f = _smallest_file(v.get("video_files", []))
            slug = str(v.get("url", "")).rstrip("/").rsplit("/", 1)[-1]
            if f and v.get("duration", 0) >= 15 and not _bad(slug):
                out.append({"key": f"px{v['id']}", "url": f["link"], "ext": ".mp4", "source": "Pexels video sesi",
                            "title": slug.replace("-", " ")[:80] or f"Pexels {v['id']}"})
    return out


def _interleave(a: list[dict], b: list[dict]) -> list[dict]:
    out, seen = [], set()
    for i in range(max(len(a), len(b))):
        for lst in (a, b):
            if i < len(lst) and lst[i]["key"] not in seen:
                seen.add(lst[i]["key"])
                out.append(lst[i])
    return out


def find_candidates(n: int = PICK_COUNT, min_crackles: float = MIN_CHOICE_CRACKLES,
                    progress=lambda _m: None) -> list[dict]:
    """En çıtırtılı n gerçek kaydı hazırla (fire_pick/cand_i.m4a). Döner: [{title, source, crackle, path}]."""
    sources = _interleave(_freesound_sources(), _pexels_sources())
    d = pick_dir()
    for old in d.iterdir():
        old.unlink()
    work = d / "_dl"
    work.mkdir(exist_ok=True)
    scored: list[tuple[float, Path, dict, tuple[float, float]]] = []
    try:
        for k, src in enumerate(sources[:MAX_DOWNLOADS]):
            raw = work / f"{k}{src['ext']}"
            try:
                stock._download(src["url"], raw)
                st = fireplace.crackle_stats(raw)
            except (requests.RequestException, subprocess.CalledProcessError, OSError) as e:
                log.warning("Ateş sesi adayı alınamadı (%s): %s", src["title"], e)
                continue
            log.info("Ateş sesi adayı: %s [%s] — %.1f çıtırtı/sn, %.0f Hz", src["title"], src["source"], *st)
            if st[0] >= min_crackles:
                scored.append((fireplace.crackle_score(st), raw, src, st))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict] = []
        for score, raw, src, st in scored:
            if len(out) >= n:
                break
            path = d / f"cand_{len(out) + 1}.m4a"
            try:
                if not fireplace.prepare_fire_sound(raw, path):
                    continue
            except fireplace.media.MediaError as e:
                log.warning("Ateş sesi adayı işlenemedi (%s): %s", src["title"], e)
                continue
            meta = {"title": src["title"], "source": src["source"], "crackle": round(st[0], 1), "path": str(path)}
            path.with_suffix(".json").write_text(json.dumps(meta))
            out.append(meta)
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def choose(i: int) -> Path:
    """i. adayı (1'den başlar) tüm videolarda kullanılacak ateş sesi yap."""
    src = pick_dir() / f"cand_{i}.m4a"
    if not src.exists():
        raise ValueError("Bu aday artık yok; /atessesi ara ile yeniden arayın")
    dst = fireplace.user_fire_sound()
    shutil.copyfile(src, dst)
    shutil.copyfile(src.with_suffix(".json"), dst.with_suffix(".json"))
    return dst


def auto_best(out: Path) -> Path | None:
    """Kimse seçmediyse: en çıtırtılı gerçek kaydı otomatik kullan."""
    cands = find_candidates(n=1, min_crackles=fireplace.MIN_CRACKLES_PER_SEC)
    if not cands:
        log.warning("Yeterince çıtırtılı gerçek ateş kaydı bulunamadı")
        return None
    src = Path(cands[0]["path"])
    shutil.copyfile(src, out)
    shutil.copyfile(src.with_suffix(".json"), out.with_suffix(".json"))
    return out
