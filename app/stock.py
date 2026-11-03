"""Temaya uygun stok video/fotoğraf (Pexels) ve bunlardan dikişsiz dönen kolaj videosu.

Pexels içerikleri ücretsizdir ve ticari kullanıma izin verir (atıf zorunlu değil;
açıklamaya yine de "Footage: Pexels" eklenir). PEXELS_API_KEY yoksa ya da yeterli
içerik bulunamazsa None döner; pipeline şömine/görsel yedeğine geçer.
"""
from __future__ import annotations

import logging
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import requests

from . import media
from .config import CONFIG
from .themes import Theme

log = logging.getLogger(__name__)

API = "https://api.pexels.com"
SEGMENT_SEC = 8.0      # kolajdaki her klip/fotoğrafın süresi
XFADE_SEC = 1.5        # aralarındaki yumuşak geçiş
N_VIDEOS = 8
N_PHOTOS = 3


@dataclass(frozen=True)
class StockItem:
    provider_id: str   # "v123" / "p456"
    kind: str          # video | photo
    path: Path


def available() -> bool:
    return bool(CONFIG.pexels_api_key)


def _get(path: str, params: dict) -> dict:
    r = requests.get(API + path, params=params, headers={"Authorization": CONFIG.pexels_api_key}, timeout=30)
    r.raise_for_status()
    return r.json()


def _download(url: str, out: Path) -> Path:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return out


def _best_file(files: list[dict]) -> dict | None:
    mp4 = [f for f in files if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")]
    landscape = [f for f in mp4 if f["width"] >= f["height"]] or mp4
    if not landscape:
        return None
    # 1920 genişliğe en yakın (çok büyük 4K dosyaları gereksiz indirmeyelim)
    return min(landscape, key=lambda f: (abs(f["width"] - 1920), -f["width"]))


def fetch(theme: Theme, dest: Path, used: set[str], rng: random.Random) -> list[StockItem]:
    """Temaya uygun klip ve fotoğrafları indir (daha önce kullanılanları atla)."""
    if not available():
        return []
    dest.mkdir(parents=True, exist_ok=True)
    items: list[StockItem] = []
    try:
        vids: list[dict] = []
        for q in rng.sample(list(theme.video_queries), len(theme.video_queries)):
            res = _get("/videos/search", {"query": q, "orientation": "landscape", "per_page": 15,
                                          "size": "medium"})
            vids += [v for v in res.get("videos", []) if v.get("duration", 0) >= SEGMENT_SEC + 1
                     and f"v{v['id']}" not in used]
        rng.shuffle(vids)
        seen: set[str] = set()
        for v in vids:
            if len([i for i in items if i.kind == "video"]) >= N_VIDEOS:
                break
            pid = f"v{v['id']}"
            f = _best_file(v.get("video_files", []))
            if pid in seen or not f:
                continue
            seen.add(pid)
            try:
                items.append(StockItem(pid, "video", _download(f["link"], dest / f"{pid}.mp4")))
            except requests.RequestException as e:
                log.warning("Pexels video indirilemedi (%s): %s", pid, e)
        photos: list[dict] = []
        for q in theme.photo_queries:
            res = _get("/v1/search", {"query": q, "orientation": "landscape", "per_page": 15})
            photos += [p for p in res.get("photos", []) if f"p{p['id']}" not in used]
        rng.shuffle(photos)
        for p in photos[:N_PHOTOS]:
            pid = f"p{p['id']}"
            url = p.get("src", {}).get("large2x") or p.get("src", {}).get("original")
            if not url:
                continue
            try:
                items.append(StockItem(pid, "photo", _download(url, dest / f"{pid}.jpg")))
            except requests.RequestException as e:
                log.warning("Pexels fotoğraf indirilemedi (%s): %s", pid, e)
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Pexels araması başarısız (%s): %s", theme.key, e)
    return items


def fetch_scene(queries: tuple[str, ...], dest: Path, used: set[str], rng: random.Random) -> StockItem | None:
    """Tek sahneli video için temaya uygun TEK bir klip (yoksa tek bir fotoğraf) indir."""
    if not available():
        return None
    dest.mkdir(parents=True, exist_ok=True)
    try:
        for q in queries:  # önce en uygun arama
            res = _get("/videos/search", {"query": q, "orientation": "landscape", "per_page": 15, "size": "medium"})
            vids = [v for v in res.get("videos", []) if v.get("duration", 0) >= 12 and f"v{v['id']}" not in used]
            for v in rng.sample(vids[:6], min(6, len(vids))):  # en alakalı ilk sonuçlardan biri
                f = _best_file(v.get("video_files", []))
                if f:
                    pid = f"v{v['id']}"
                    return StockItem(pid, "video", _download(f["link"], dest / f"{pid}.mp4"))
        for q in queries:
            res = _get("/v1/search", {"query": q, "orientation": "landscape", "per_page": 15})
            photos = [p for p in res.get("photos", []) if f"p{p['id']}" not in used]
            if photos:
                p = rng.choice(photos[:6])
                url = p.get("src", {}).get("large2x") or p.get("src", {}).get("original")
                if url:
                    return StockItem(f"p{p['id']}", "photo", _download(url, dest / f"p{p['id']}.jpg"))
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Pexels sahne araması başarısız: %s", e)
    return None


def _segment(item: StockItem, out: Path, size: tuple[int, int]) -> Path:
    w, h = size
    frames = int(SEGMENT_SEC * media.FPS)
    if item.kind == "video":
        dur = media.duration(item.path)
        start = max(0.0, (dur - SEGMENT_SEC) / 2)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={media.FPS},"
              "format=yuv420p,setsar=1")
        media.run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{SEGMENT_SEC:.2f}", "-i", str(item.path),
                   "-vf", vf, "-an", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "20", str(out)])
    else:  # fotoğraf: yavaş Ken Burns yakınlaşması
        vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
              f"zoompan=z='1.0+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
              f"s={w}x{h}:fps={media.FPS},format=yuv420p,setsar=1")
        media.run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(media.FPS), "-t", f"{SEGMENT_SEC:.2f}",
                   "-i", str(item.path), "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "20", str(out)])
    return out


def build_collage(items: list[StockItem], out: Path, size: tuple[int, int] = (1920, 1080)) -> Path:
    """Klip ve fotoğrafları yumuşak geçişlerle birleştir; sonu başına bindirilerek atlamasız döner."""
    from .fireplace import seamless_video_loop

    if len(items) < 3:
        raise media.MediaError("Kolaj için en az 3 klip/fotoğraf gerekli")
    work = out.parent / f"_segs_{out.stem}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        # fotoğrafları videoların arasına dağıt
        vids = [i for i in items if i.kind == "video"]
        photos = [i for i in items if i.kind == "photo"]
        order: list[StockItem] = []
        step = max(1, len(vids) // (len(photos) + 1)) if photos else 0
        for n, v in enumerate(vids, 1):
            order.append(v)
            if photos and n % step == 0:
                order.append(photos.pop(0))
        order += photos
        segs = [_segment(it, work / f"s{n:02d}.mp4", size) for n, it in enumerate(order)]

        cmd = ["ffmpeg", "-y"]
        for s in segs:
            cmd += ["-i", str(s)]
        parts, prev, acc = [], "[0:v]", SEGMENT_SEC
        for n in range(1, len(segs)):
            label = f"[x{n}]"
            parts.append(f"{prev}[{n}:v]xfade=transition=fade:duration={XFADE_SEC}:offset={acc - XFADE_SEC:.3f}"
                         f"{label}")
            prev, acc = label, acc + SEGMENT_SEC - XFADE_SEC
        raw = work / "raw.mp4"
        cmd += ["-filter_complex", ";".join(parts), "-map", prev, "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", "-pix_fmt", "yuv420p", str(raw)]
        media.run(cmd)
        return seamless_video_loop(raw, out, size, max_seconds=acc + 1, xfade=XFADE_SEC)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def credits_line() -> str:
    return "Footage: Pexels (pexels.com)"
