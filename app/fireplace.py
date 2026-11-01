"""Şömine modu: arka plan döngüsü + ateş çıtırtısı sesi.

Arka plan kaynakları (öncelik sırasıyla, her videoda rastgele biri seçilir):
1. Telegram'dan gönderilen şömine VİDEOLARI  -> dikişsiz döngüye çevrilir (en gerçekçi)
2. Telegram'dan gönderilen şömine FOTOĞRAFLARI ve repodaki `assets/fireplace/` fotoğrafları
   -> alevler dalgalanan, ışığı titreyen, korları nabız gibi atan dikişsiz animasyona çevrilir

Ateş sesi kaynakları (öncelik sırasıyla):
1. Gönderilen şömine videosunun kendi sesi (sessiz değilse)
2. ElevenLabs ses efekti (ELEVENLABS_API_KEY varsa bir kez üretilip saklanır)
3. Prosedürel çıtırtı sentezi (her zaman çalışır)

Hazırlanan dosyalar `DATA_DIR/assets/cache` içinde saklanır; her videoda yeniden üretilmez.
"""
from __future__ import annotations

import hashlib
import logging
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageFilter

from . import media
from .config import CONFIG

log = logging.getLogger(__name__)

BUNDLED_DIR = Path(__file__).resolve().parent.parent / "assets" / "fireplace"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
FIRE_LOOP_SECONDS = 12
LOOP_CRF = 27  # ateş çok detaylı; 23'te 3 saatlik video ~4,7 GB olur, 27'de ~2,5 GB
CRACKLE_SECONDS = 60
SR = 44100


def user_dir() -> Path:
    d = CONFIG.data_dir / "assets" / "fireplace"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = CONFIG.data_dir / "assets" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass(frozen=True)
class Background:
    kind: str   # "video" | "image"
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


def backgrounds() -> list[Background]:
    """Kullanılabilir arka planlar: kullanıcı videoları varsa yalnızca onlar, yoksa fotoğraflar."""
    videos = sorted(p for p in user_dir().iterdir() if p.suffix.lower() in VIDEO_EXT)
    if BUNDLED_DIR.exists():  # GitHub'a assets/fireplace/ altına yüklenen videolar
        videos += sorted(p for p in BUNDLED_DIR.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if videos:
        return [Background("video", p) for p in videos]
    photos = sorted(p for p in user_dir().iterdir() if p.suffix.lower() in IMAGE_EXT)
    if BUNDLED_DIR.exists():
        photos += sorted(p for p in BUNDLED_DIR.iterdir() if p.suffix.lower() in IMAGE_EXT)
    return [Background("image", p) for p in photos]


def pick_background(rng: random.Random, avoid: str | None = None) -> Background | None:
    pool = backgrounds()
    if len(pool) > 1 and avoid:
        pool = [b for b in pool if b.name != avoid] or pool
    return rng.choice(pool) if pool else None


def find_background(name: str) -> Background | None:
    return next((b for b in backgrounds() if b.name == name), None)


def _key(path: Path, *extra: object) -> str:
    st = path.stat()
    raw = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}|{'|'.join(map(str, extra))}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------- görsel
def cover(image: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(image).convert("RGB")
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def still_frame(bg: Background, out: Path, size: tuple[int, int] = (1920, 1080)) -> Path:
    """Küçük resim ve dikey kesit için tek kare."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if bg.kind == "image":
        cover(bg.path, size).save(out)
        return out
    dur = media.duration(bg.path)
    tmp = out.with_suffix(".frame.png")
    media.run(["ffmpeg", "-y", "-ss", f"{dur * 0.4:.2f}", "-i", str(bg.path), "-frames:v", "1", str(tmp)])
    cover(tmp, size).save(out)
    tmp.unlink(missing_ok=True)
    return out


def loop_for(bg: Background, size: tuple[int, int]) -> Path:
    """Arka plan için (önbellekli) dikişsiz döngü klibi."""
    w, h = size
    out = cache_dir() / f"loop_{_key(bg.path, w, h, LOOP_CRF, 'flicker-v2')}.mp4"
    if out.exists():
        return out
    tmp = out.with_suffix(".tmp.mp4")
    if bg.kind == "video":
        seamless_video_loop(bg.path, tmp, size)
    else:
        animate_fire(bg.path, tmp, size)
    tmp.rename(out)
    return out


def seamless_video_loop(src: Path, out: Path, size: tuple[int, int], max_seconds: float = 40.0,
                        xfade: float = 1.5) -> Path:
    """Videonun sonunu başına yumuşakça bindirerek atlamasız tekrar eden bir döngü yap (sessiz)."""
    w, h = size
    length = min(max_seconds, media.duration(src))
    if length < 4:
        raise media.MediaError("Video çok kısa (en az 4 sn olmalı)")
    x = min(xfade, length / 4)
    fc = (
        f"[0:v]trim=0:{length:.3f},setpts=PTS-STARTPTS,"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={media.FPS},format=yuv420p,"
        "split=3[a][b][c];"
        f"[a]trim={x:.3f}:{length - x:.3f},setpts=PTS-STARTPTS[mid];"
        f"[b]trim={length - x:.3f}:{length:.3f},setpts=PTS-STARTPTS[tail];"
        f"[c]trim=0:{x:.3f},setpts=PTS-STARTPTS[head];"
        f"[tail][head]xfade=transition=fade:duration={x:.3f}:offset=0[blend];"
        "[mid][blend]concat=n=2:v=1:a=0[out]"
    )
    media.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[out]", "-an",
               "-c:v", "libx264", "-preset", "slow", "-crf", str(LOOP_CRF), "-g", str(media.FPS * 2),
               "-pix_fmt", "yuv420p", str(out)])
    return out


def _blur(arr: np.ndarray, radius: float) -> np.ndarray:
    """0..1 float diziyi PIL ile bulanıklaştır (2B ya da 3 kanallı)."""
    if arr.ndim == 2:
        im = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "L")
        return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255
    im = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGB")
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def animate_fire(image: Path, out: Path, size: tuple[int, int] = (1920, 1080),
                 seconds: int | None = None, seed: int = 7) -> Path:
    """Şömine fotoğrafını canlandır: alevler yukarı doğru dalgalanır, ışık titrer, korlar nabız atar.

    Tüm hareketler döngü süresinin tam katı frekanslarla yapılır; klip atlamasız tekrar eder.
    """
    w, h = size
    seconds = seconds or FIRE_LOOP_SECONDS
    rng = np.random.default_rng(seed)
    img = np.asarray(cover(image, size), dtype=np.float32) / 255
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    warm = np.clip(r - b, 0, 1)

    flame = _smoothstep(0.35, 0.8, lum) * _smoothstep(0.05, 0.3, warm)        # parlak sarı-turuncu alev
    ember = _smoothstep(0.25, 0.55, r) * _smoothstep(0.15, 0.45, r - g)       # kırmızı korlar
    flame_soft = _blur(flame, max(4, w / 300))
    glow = _blur(img * flame[..., None], max(30, w / 30))                    # odaya vuran sıcak ışık

    frames = seconds * media.FPS
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    s = h / 1080  # çözünürlükten bağımsız ölçek
    ph = rng.uniform(0, 2 * np.pi, 12)

    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(media.FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(LOOP_CRF), "-g", str(media.FPS * 2),
           "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for n in range(frames):
            p = 2 * np.pi * n / frames  # 0..2π, döngü boyunca
            # Alevler: yukarı akan dalgalar (y ile faz kayar) -> yükselme hissi
            frame = img  # alevler bükülmez (yapay görünüyordu); yalnızca ışık titrer, korlar parlar

            flick = (0.5 * np.sin(p * 11 + ph[4]) + 0.3 * np.sin(p * 23 + ph[5]) + 0.2 * np.sin(p * 37 + ph[6]))
            flick2 = (0.6 * np.sin(p * 17 + ph[7]) + 0.4 * np.sin(p * 31 + ph[8]))
            pulse = 0.5 + 0.5 * np.sin(xs / (70 * s) + p * 5 + ph[9]) * np.sin(ys / (40 * s) - p * 4 + ph[10])
            gain = (1 + 0.05 * flick + flame_soft * (0.12 * flick2) + ember * (0.22 * (pulse - 0.5)))[..., None]
            frame = frame * gain + glow * (0.35 + 0.15 * flick)
            proc.stdin.write((np.clip(frame, 0, 1) * 255).astype(np.uint8).tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise media.MediaError(f"Ateş animasyonu kodlanamadı:\n{err[-1200:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out


# ---------------------------------------------------------------------------- ses
def ambience_bed() -> Path:
    """Mixin altına döşenecek, dikişsiz tekrar eden ateş sesi (önbellekli)."""
    for bg in backgrounds():  # 1) kullanıcı videosunun kendi sesi
        if bg.kind == "video":
            out = cache_dir() / f"fire_audio_{_key(bg.path)}.m4a"
            if out.exists():
                return out
            try:
                if _extract_fire_audio(bg.path, out):
                    return out
            except media.MediaError as e:
                log.warning("Videodan ateş sesi alınamadı: %s", e)
    out = cache_dir() / "fire_elevenlabs.m4a"  # 2) ElevenLabs ses efekti
    if out.exists():
        return out
    if CONFIG.elevenlabs_api_key and not CONFIG.dry_run:
        try:
            return _elevenlabs_fire(out)
        except Exception as e:  # noqa: BLE001
            log.warning("ElevenLabs ateş sesi üretilemedi (%s), sentez kullanılacak", e)
    out = cache_dir() / "fire_procedural_v2.m4a"  # 3) sentez
    if not out.exists():
        synth_crackle(out)
    return out


def _mean_volume(path: Path) -> float:
    proc = subprocess.run(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return -99.0


def _extract_fire_audio(video: Path, out: Path) -> bool:
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                "stream=index", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    if not has_audio.stdout.strip():
        return False
    raw = out.with_suffix(".raw.wav")
    media.run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", str(SR), "-t", "120", str(raw)])
    try:
        if _mean_volume(raw) < -55:
            return False
        seamless_audio_loop(raw, out)
        return True
    finally:
        raw.unlink(missing_ok=True)


def _elevenlabs_fire(out: Path) -> Path:
    resp = requests.post(
        "https://api.elevenlabs.io/v1/sound-generation",
        headers={"xi-api-key": CONFIG.elevenlabs_api_key, "Content-Type": "application/json"},
        json={"text": "Cozy wood fireplace burning steadily indoors, gentle crackling and soft popping of logs, "
                      "warm low flame rumble, continuous ambience, no music, no voices",
              "duration_seconds": 20, "prompt_influence": 0.6},
        timeout=180,
    )
    if resp.status_code != 200 or not resp.content:
        raise RuntimeError(f"ElevenLabs {resp.status_code}: {resp.text[:200]}")
    raw = out.with_suffix(".raw.mp3")
    raw.write_bytes(resp.content)
    try:
        seamless_audio_loop(raw, out, xfade=3.0)
    finally:
        raw.unlink(missing_ok=True)
    return out


def seamless_audio_loop(src: Path, out: Path, xfade: float = 2.0) -> Path:
    """Sesin sonunu başına bindirerek tekrarında atlama olmayan döngü yap; -20 LUFS'e normalize et."""
    length = media.duration(src)
    x = min(xfade, length / 4)
    fc = (
        f"[0:a]asplit=3[a][b][c];"
        f"[a]atrim={x:.3f}:{length - x:.3f},asetpts=PTS-STARTPTS[mid];"
        f"[b]atrim={length - x:.3f}:{length:.3f},asetpts=PTS-STARTPTS[tail];"
        f"[c]atrim=0:{x:.3f},asetpts=PTS-STARTPTS[head];"
        f"[tail][head]acrossfade=d={x:.3f}:c1=qsin:c2=qsin[blend];"
        "[mid][blend]concat=n=2:v=0:a=1,loudnorm=I=-20:TP=-2:LRA=11[out]"
    )
    media.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[out]", "-ar", str(SR),
               "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(out)])
    return out


def _fft_filter(x: np.ndarray, lo: float | None, hi: float | None, slope: float = 0.0) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = np.ones_like(f)
    if lo:
        gain *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        gain *= 1 / (1 + (f / hi) ** 4)
    if slope:
        gain *= (np.maximum(f, 20) / 1000) ** slope
    return np.fft.irfft(spec * gain, len(x))


def synth_crackle(out: Path, seconds: int | None = None, seed: int = 11) -> Path:
    """Prosedürel şömine sesi: alçak alev uğultusu + hafif hışırtı + rastgele odun çıtırtıları ve patlamaları."""
    seconds = seconds or CRACKLE_SECONDS
    rng = np.random.default_rng(seed)
    pad = 3
    n = (seconds + pad) * SR
    t = np.arange(n) / SR
    period = 2 * np.pi / seconds

    def slow_mod(k: int, depth: float) -> np.ndarray:
        m = np.ones(n)
        for i in range(1, k + 1):
            m += depth / i * np.sin(period * (i * 3) * t + rng.uniform(0, 6.3))
        return np.clip(m, 0.2, None)

    out_lr = np.zeros((n, 2))
    for ch in range(2):
        roar = _fft_filter(rng.standard_normal(n), 30, 280, slope=-1.0)
        roar *= 0.22 / np.std(roar) * slow_mod(4, 0.35)
        hiss = _fft_filter(rng.standard_normal(n), 1800, 6500)
        hiss *= 0.01 / np.std(hiss) * slow_mod(3, 0.5)
        out_lr[:, ch] = roar + hiss

    def add_event(at: int, sig: np.ndarray, pan: float) -> None:
        end = min(n, at + len(sig))
        out_lr[at:end, 0] += sig[: end - at] * (1 - pan) / 2
        out_lr[at:end, 1] += sig[: end - at] * (1 + pan) / 2

    count = int(seconds * rng.uniform(4.5, 6.5))
    for at in rng.uniform(0, seconds + pad - 0.2, count):
        amp = min(1.0, 0.07 * (rng.pareto(2.2) + 1))
        pan = rng.uniform(-0.7, 0.7)
        group = 1 if rng.random() > 0.3 else rng.integers(2, 7)
        for k in range(group):
            start = int((at + (k * rng.uniform(0.004, 0.05) if k else 0)) * SR)
            ln = int(SR * rng.uniform(0.002, 0.02))
            env = np.exp(-np.arange(ln) / (SR * rng.uniform(0.0008, 0.005)))
            burst = rng.standard_normal(ln) * env
            burst = np.diff(burst, prepend=0) * 0.25 + burst * 0.75  # yumuşak "pıt" (tizi az)
            add_event(start, burst * amp * (0.6 if k else 1.0), pan)
        if amp > 0.25 and rng.random() < 0.5:  # büyük odun patlaması: kısa gövde sesi
            ln = int(SR * 0.06)
            tt = np.arange(ln) / SR
            body = np.sin(2 * np.pi * rng.uniform(180, 600) * tt) * np.exp(-tt / 0.012) * amp * 0.5
            add_event(int(at * SR), body, pan)

    # Dikişsiz döngü: son `pad` saniyeyi başa bindir
    x = pad * SR
    fade = np.linspace(0, 1, x)[:, None]
    head = out_lr[:x] * fade + out_lr[-x:] * (1 - fade)
    loop = np.concatenate([head, out_lr[x:-x]])[: seconds * SR]
    loop /= np.max(np.abs(loop)) * 1.05
    raw = out.with_suffix(".f32")
    loop.astype("<f4").tofile(raw)
    try:
        media.run(["ffmpeg", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(raw),
                   "-af", "lowpass=f=4500,highshelf=f=2500:g=-4,loudnorm=I=-20:TP=-2:LRA=11", "-ar", str(SR),
                   "-c:a", "aac", "-b:a", "160k", str(out)])
    finally:
        raw.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------------------- yükleme (Telegram)
def save_upload(src: Path, original_name: str) -> Background:
    """Telegram'dan gelen dosyayı arka plan kütüphanesine kaydet ve doğrula."""
    ext = Path(original_name).suffix.lower() or src.suffix.lower()
    if ext not in IMAGE_EXT | VIDEO_EXT:
        raise ValueError("Desteklenmeyen dosya türü (jpg/png/webp ya da mp4/mov gönderin)")
    stem = "".join(c if c.isalnum() else "_" for c in Path(original_name).stem)[:30] or "upload"
    dest = user_dir() / f"{stem}_{hashlib.sha1(src.read_bytes()).hexdigest()[:6]}{ext}"
    shutil.move(str(src), dest)
    bg = Background("video" if ext in VIDEO_EXT else "image", dest)
    try:
        loop_for(bg, (1920, 1080))  # şimdi hazırla (önbelleğe girer); hatalıysa hemen söyle
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return bg


def remove(name: str) -> bool:
    p = user_dir() / name
    if p.exists() and p.parent == user_dir():
        p.unlink()
        return True
    return False
