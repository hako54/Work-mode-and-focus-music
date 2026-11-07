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
SEGMENT_SEC = 14.0     # kolajdaki her klip/fotoğrafın süresi (sakin: uzun sahneler)
XFADE_SEC = 3.0        # aralarındaki yumuşak geçiş
N_VIDEOS = 5
N_PHOTOS = 2
SLOW_DEFAULT = 1.25    # 24-30 fps kliplerde hafif ağır çekim
SLOW_MAX = 2.0         # 50-60 fps kliplerde akıcı 2x ağır çekim
NO_SPEEDUP = ("timelapse", "time lapse", "hyperlapse", "fast motion", "speed")


@dataclass(frozen=True)
class StockItem:
    provider_id: str   # "v123" / "p456"
    kind: str          # video | photo
    path: Path
    slow: float = 1.0  # ağır çekim katsayısı (2.0 = yarı hız)


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
    # 1920 genişliğe yakın (4K gereksiz) ve mümkünse 50-60 fps (akıcı ağır çekim için)
    return min(landscape, key=lambda f: (abs(f["width"] - 1920) // 400, -(f.get("fps") or 30), -f["width"]))


def slow_factor(f: dict) -> float:
    """60 fps klip 2x ağır çekime akıcı dayanır; 24-30 fps klipler hafifçe yavaşlatılır."""
    fps = float(f.get("fps") or 30)
    return min(SLOW_MAX, round(fps / media.FPS, 1)) if fps >= 45 else SLOW_DEFAULT


def _calm(v: dict) -> bool:
    """Hızlandırılmış (timelapse vb.) klipleri ele."""
    text = " ".join(str(v.get(k, "")) for k in ("url", "tags")).lower()
    return not any(w in text for w in NO_SPEEDUP)


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
            vids += [v for v in res.get("videos", []) if v.get("duration", 0) >= SEGMENT_SEC / SLOW_DEFAULT + 1
                     and f"v{v['id']}" not in used and _calm(v)]
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
                items.append(StockItem(pid, "video", _download(f["link"], dest / f"{pid}.mp4"), slow_factor(f)))
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


def fetch_photos(queries: tuple[str, ...], dest: Path, used: set[str], rng: random.Random,
                 n: int = 3) -> list[StockItem]:
    """Kapak adayları: her aramadan bir tane olacak şekilde n fotoğraf (yatay, daha önce kullanılmamış)."""
    if not available():
        return []
    dest.mkdir(parents=True, exist_ok=True)
    out: list[StockItem] = []
    seen: set[str] = set()
    try:
        pools = []
        for q in queries:
            res = _get("/v1/search", {"query": q, "orientation": "landscape", "per_page": 15})
            pools.append([p for p in res.get("photos", []) if f"p{p['id']}" not in used])
        while len(out) < n and any(pools):
            for pool in pools:
                if len(out) >= n:
                    break
                while pool:
                    p = pool.pop(rng.randrange(min(len(pool), 5)))  # en alakalı ilk sonuçlardan
                    pid = f"p{p['id']}"
                    url = p.get("src", {}).get("large2x") or p.get("src", {}).get("original")
                    if pid in seen or not url:
                        continue
                    seen.add(pid)
                    try:
                        out.append(StockItem(pid, "photo", _download(url, dest / f"{pid}.jpg")))
                    except requests.RequestException as e:
                        log.warning("Kapak fotoğrafı indirilemedi (%s): %s", pid, e)
                        continue
                    break
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Pexels kapak araması başarısız: %s", e)
    return out


def fetch_scene(queries: tuple[str, ...], dest: Path, used: set[str], rng: random.Random,
                allow_photo: bool = False) -> StockItem | None:
    """Tek sahneli video için temaya uygun TEK bir klip indir (allow_photo: yoksa tek fotoğraf)."""
    if not available():
        return None
    dest.mkdir(parents=True, exist_ok=True)
    try:
        for q in queries:  # önce en uygun arama
            res = _get("/videos/search", {"query": q, "orientation": "landscape", "per_page": 15, "size": "medium"})
            vids = [v for v in res.get("videos", []) if v.get("duration", 0) >= 12 and f"v{v['id']}" not in used
                    and _calm(v)]
            for v in rng.sample(vids[:6], min(6, len(vids))):  # en alakalı ilk sonuçlardan biri
                f = _best_file(v.get("video_files", []))
                if f:
                    pid = f"v{v['id']}"
                    return StockItem(pid, "video", _download(f["link"], dest / f"{pid}.mp4"), slow_factor(f))
        for q in (queries if allow_photo else ()):
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


def fetch_scene_clips(queries: tuple[str, ...], dest: Path, used: set[str], rng: random.Random,
                      n: int = 3) -> list[StockItem]:
    """Aynı temadan farklı çekimler, en fazla n video. Her aramadan en fazla birkaç klip alınır ki
    sahneler çeşitlensin; aramalar biterse ikinci turda kalanlardan tamamlanır."""
    if not available():
        return []
    dest.mkdir(parents=True, exist_ok=True)
    out: list[StockItem] = []
    per_query = max(2, -(-n // max(1, len(queries))))
    pools: list[list[dict]] = []
    leftovers: list[dict] = []
    for q in queries:
        try:
            res = _get("/videos/search", {"query": q, "orientation": "landscape", "per_page": 20, "size": "medium"})
        except (requests.RequestException, ValueError) as e:
            log.warning("Pexels sahne araması başarısız (%s): %s", q, e)
            continue
        vids = [v for v in res.get("videos", []) if v.get("duration", 0) >= 12 and f"v{v['id']}" not in used
                and _calm(v)]
        vids = rng.sample(vids[:12], min(12, len(vids)))
        pools.append(vids[:per_query])
        leftovers += vids[per_query:]
    # aramalar arasında sırayla (çift sahnesi, mekân, çift, mekân…), sonra kalanlar
    order = [pool[i] for i in range(per_query) for pool in pools if i < len(pool)] + leftovers
    seen: set[int] = set()
    for v in order:
        if len(out) >= n:
            break
        if v.get("id") in seen:
            continue
        seen.add(v.get("id"))
        f = _best_file(v.get("video_files", []))
        if not f:
            continue
        pid = f"v{v['id']}"
        try:
            out.append(StockItem(pid, "video", _download(f["link"], dest / f"{pid}.mp4"), slow_factor(f)))
        except requests.RequestException as e:
            log.warning("Sahne klibi indirilemedi (%s): %s", pid, e)
    return out


_ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-g", str(media.FPS * 2), "-pix_fmt", "yuv420p"]


def pingpong_loop(src: Path, out: Path, size: tuple[int, int], chunk: float = 3.0) -> Path:
    """Bumerang döngüsü: ileri + geri; sonu başına doğal akar, hiç 'başa sarma' olmaz, süre iki katına çıkar.

    Tüm klibi tek seferde ters çevirmek çok RAM ister; kısa parçalar ayrı ayrı ters çevrilip birleştirilir."""
    w, h = size
    work = out.parent / f"_pp_{out.stem}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        fwd = work / "fwd.mp4"
        media.run(["ffmpeg", "-y", "-i", str(src), "-vf",
                   f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={media.FPS},"
                   "format=yuv420p,setsar=1", "-an", *_ENC, str(fwd)])
        length = media.duration(fwd)
        parts: list[Path] = []
        start, n = 0.0, 0
        while start < length - 0.05:
            seg = work / f"rev_{n:03d}.mp4"
            media.run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{min(chunk, length - start):.3f}",
                       "-i", str(fwd), "-vf", "reverse", "-an", *_ENC, str(seg)])
            parts.append(seg)
            start += chunk
            n += 1
        playlist = work / "list.txt"
        playlist.write_text("".join(f"file '{p}'\n" for p in [fwd, *reversed(parts)]))
        tmp = out.with_name(out.stem + ".part.mp4")
        media.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(playlist), "-c", "copy",
                   "-movflags", "+faststart", str(tmp)])
        tmp.replace(out)
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _segment(item: StockItem, out: Path, size: tuple[int, int], seg_sec: float | None = None) -> Path:
    w, h = size
    SEGMENT = seg_sec or SEGMENT_SEC
    frames = int(SEGMENT * media.FPS)
    if item.kind == "video":
        dur = media.duration(item.path)
        slow = max(1.0, min(item.slow, dur / (SEGMENT + 0.5)))  # kısa klipte süre yetmezse daha az yavaşlat
        src_len = SEGMENT / slow
        start = max(0.0, (dur - src_len) / 2)
        vf = (f"setpts={slow:.4f}*PTS,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"fps={media.FPS},format=yuv420p,setsar=1")
        media.run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{src_len + 0.5:.2f}", "-i", str(item.path),
                   "-vf", vf, "-an", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "20", str(out)])
    else:  # fotoğraf: yavaş Ken Burns yakınlaşması
        vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
              f"zoompan=z='1.0+0.04*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
              f"s={w}x{h}:fps={media.FPS},format=yuv420p,setsar=1")
        media.run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(media.FPS), "-t", f"{SEGMENT:.2f}",
                   "-i", str(item.path), "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "20", str(out)])
    return out


def slow_down(item: StockItem, out: Path, max_out: float = 40.0) -> Path:
    """Tek sahne klibini ağır çekime al (setpts); en fazla max_out saniyelik çıktı."""
    dur = media.duration(item.path)
    slow = max(1.0, item.slow)
    src_len = min(dur, max_out / slow)
    media.run(["ffmpeg", "-y", "-t", f"{src_len:.2f}", "-i", str(item.path),
               "-vf", f"setpts={slow:.4f}*PTS,fps={media.FPS},format=yuv420p", "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return out


def build_collage(items: list[StockItem], out: Path, size: tuple[int, int] = (1920, 1080),
                  seg_sec: float | None = None, xfade: float | None = None, min_items: int = 3) -> Path:
    """Klip ve fotoğrafları yumuşak geçişlerle birleştir; sonu başına bindirilerek atlamasız döner.

    seg_sec/xfade: her çekimin süresi ve geçiş (tek sahnenin çoklu çekimi için daha uzun)."""
    from .fireplace import seamless_video_loop

    seg_len = seg_sec or SEGMENT_SEC
    xf = xfade or XFADE_SEC
    if len(items) < min_items:
        raise media.MediaError(f"En az {min_items} klip/fotoğraf gerekli")
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
        segs = [_segment(it, work / f"s{n:02d}.mp4", size, seg_len) for n, it in enumerate(order)]

        cmd = ["ffmpeg", "-y"]
        for s in segs:
            cmd += ["-i", str(s)]
        parts, prev, acc = [], "[0:v]", seg_len
        for n in range(1, len(segs)):
            label = f"[x{n}]"
            parts.append(f"{prev}[{n}:v]xfade=transition=fade:duration={xf}:offset={acc - xf:.3f}"
                         f"{label}")
            prev, acc = label, acc + seg_len - xf
        raw = work / "raw.mp4"
        cmd += ["-filter_complex", ";".join(parts), "-map", prev, "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "20", "-pix_fmt", "yuv420p", str(raw)]
        media.run(cmd)
        return seamless_video_loop(raw, out, size, max_seconds=acc + 1, xfade=xf)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def credits_line() -> str:
    return "Footage: Pexels (pexels.com)"
