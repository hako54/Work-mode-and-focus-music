"""Sinematik işleme (isteğe bağlı): sıcak renk tonu, vinyet, film greni,
temaya göre süzülen parçacıklar (şöminede kıvılcım, kışta kar, diğerlerinde ışık tozu) ve
mum/şömine sahnelerinde hafif ışık titreşimi.

Her hareket döngü süresine (L) tam bölünen periyotlarla tanımlanır: klip sonsuz tekrarlandığında
ne kayma ne de parçacıklar atlar. Parçacıklar numpy ile düşük çözünürlükte çizilip ffmpeg'e boru
ile verilir ve "screen" karışımıyla eklenir (siyah = etkisiz).
"""
from __future__ import annotations

import math
import subprocess
import threading
from pathlib import Path

import numpy as np

from . import media

PW, PH = 640, 360          # parçacık katmanı çözünürlüğü (yumuşak ışık için büyütülür)
PARTICLE_FPS = 15          # parçacık katmanı kare hızı (ana video 30 fps; araya kare tekrar edilir)
IMAGE_LOOP_SEC = 40.0      # yapay zeka görselinden yapılan döngünün süresi

# tema -> parçacık türü
THEME_PARTICLES = {"fireplace": "embers", "candlelight": "embers", "winter": "snow",
                   "rain": None, "city_night": "dust"}
FLICKER_THEMES = {"fireplace", "candlelight"}
# parçacık türü -> (renk çarpanları r, g, b)
TINT = {"embers": (1.0, 0.55, 0.18), "snow": (0.95, 0.97, 1.0), "dust": (1.0, 0.86, 0.62)}


def particles_for(theme_key: str | None) -> str | None:
    return THEME_PARTICLES.get(theme_key or "", "dust")


def _sprite(radius: float) -> np.ndarray:
    r = max(1, int(math.ceil(radius * 2.5)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return np.exp(-(xx ** 2 + yy ** 2) / (2 * radius ** 2)).astype(np.float32)


class _Particles:
    """Periyodik (L saniyede bir aynı hâle dönen) parçacık alanı."""

    def __init__(self, kind: str, length: float, seed: int = 7):
        rng = np.random.default_rng(seed)
        self.kind, self.L = kind, length
        if kind == "snow":
            n, travel, sizes, bright = 140, (10.0, 22.0), (0.8, 2.6), (0.35, 0.85)
        elif kind == "embers":
            n, travel, sizes, bright = 40, (7.0, 14.0), (1.0, 2.0), (1.0, 1.6)
        else:  # dust: büyük, soluk, yavaş bokeh
            n, travel, sizes, bright = 40, (25.0, 60.0), (1.5, 5.0), (0.08, 0.28)
        self.n = n
        self.x0 = rng.uniform(0, PW, n)
        self.y0 = rng.uniform(0, PH, n)
        # bir geçişin süresi -> döngüde tam sayı kadar geçiş (periyodiklik)
        self.cycles = np.maximum(1, np.round(length / rng.uniform(*travel, n))).astype(int)
        self.sway_k = rng.integers(1, 4, n)                       # yatay salınım (tam sayı periyot)
        self.sway_a = rng.uniform(4, 18, n) * (2.0 if kind == "dust" else 1.0)
        self.phase = rng.uniform(0, 2 * math.pi, n)
        self.off = rng.uniform(0, 1, n)                           # her parçacık geçişin farklı yerinde
        self.flick_k = rng.integers(3, 12, n)                     # parlaklık titreşimi
        self.bright = rng.uniform(*bright, n)
        self.radius = rng.uniform(*sizes, n)
        self.sprites = [_sprite(r) for r in self.radius]
        if kind == "embers":  # kıvılcımlar alttan doğar ve sönerek yükselir
            self.x0 = rng.uniform(PW * 0.15, PW * 0.85, n)
        if kind == "dust":    # toz yönü rastgele (yukarı/aşağı), çok yavaş: döngüde en fazla bir tur
            self.dy = rng.choice([-1, 1], n)
            self.cycles = np.ones(n, dtype=int)

    def frame(self, t: float) -> np.ndarray:
        img = np.zeros((PH, PW), np.float32)
        u = t / self.L
        tau = 2 * math.pi * u
        for i in range(self.n):
            prog = (u * self.cycles[i] + self.off[i]) % 1.0
            sway = self.sway_a[i] * math.sin(self.sway_k[i] * tau + self.phase[i])
            b = self.bright[i]
            if self.kind == "snow":
                y = (self.y0[i] + prog * (PH + 20)) % (PH + 20) - 10
                x = (self.x0[i] + sway) % PW
            elif self.kind == "embers":
                y = PH + 10 - prog * (PH * 0.75)
                x = self.x0[i] + sway * 1.5
                b *= (1 - prog) ** 1.5 * (0.75 + 0.25 * math.sin(self.flick_k[i] * tau + self.phase[i]))
            else:
                x = (self.x0[i] + sway) % PW
                y = (self.y0[i] + self.dy[i] * prog * PH) % PH
                b *= 0.6 + 0.4 * math.sin(self.flick_k[i] * tau / 2 + self.phase[i]) ** 2
            s = self.sprites[i]
            r = s.shape[0] // 2
            xi, yi = int(round(x)), int(round(y))
            x1, y1, x2, y2 = xi - r, yi - r, xi + r + 1, yi + r + 1
            if x2 <= 0 or y2 <= 0 or x1 >= PW or y1 >= PH:
                continue
            sx1, sy1 = max(0, -x1), max(0, -y1)
            sx2, sy2 = s.shape[1] - max(0, x2 - PW), s.shape[0] - max(0, y2 - PH)
            img[max(0, y1):min(PH, y2), max(0, x1):min(PW, x2)] += b * s[sy1:sy2, sx1:sx2]
        return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def _fit(size: tuple[int, int]) -> str:
    """Sabit kadraj: kamera hareketi yok (yalnızca boyuta oturt)."""
    w, h = size
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


GRADE = ("colorbalance=rs=0.035:gs=0.008:bs=-0.04:rm=0.03:gm=0.005:bm=-0.03:rh=0.02:bh=-0.02,"
         "eq=contrast=1.04:saturation=1.06")


def cinematic(src: Path, out: Path, size: tuple[int, int] = (1920, 1080), theme_key: str | None = None,
              length: float | None = None, seed: int = 7) -> Path:
    """Video ya da görselden sinematik, dikişsiz döngü klibi üret (sessiz)."""
    w, h = size
    is_image = src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    L = length or (IMAGE_LOOP_SEC if is_image else media.duration(src))
    L = round(L * media.FPS) / media.FPS
    kind = particles_for(theme_key)
    flicker = (theme_key in FLICKER_THEMES)
    inp = (["-loop", "1", "-framerate", str(media.FPS), "-t", f"{L:.3f}", "-i", str(src)] if is_image
           else ["-i", str(src)])
    chain = (f"[0:v]fps={media.FPS},trim=0:{L:.3f},setpts=PTS-STARTPTS,{_fit(size)},{GRADE}"
             + (f",eq=brightness='0.012*sin(2*PI*7*t/{L:.3f})+0.008*sin(2*PI*17*t/{L:.3f})':eval=frame"
                if flicker else "")
             + ",format=gbrp[base]")
    if kind:
        r, g, b = TINT[kind]
        chain += (f";[1:v]fps={media.FPS},scale={w}:{h}:flags=bicubic,format=gbrp,"
                  f"colorchannelmixer=rr={r}:gg={g}:bb={b}[parts];"
                  "[base][parts]blend=all_mode=screen[mix];[mix]")
    else:
        chain += ";[base]"
    chain += "vignette=PI/5,noise=alls=4:allf=t,format=yuv420p[out]"
    cmd = ["ffmpeg", "-y", *inp]
    if kind:
        cmd += ["-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{PW}x{PH}", "-r", str(PARTICLE_FPS), "-i", "-"]
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd += ["-filter_complex", chain, "-map", "[out]", "-an", "-t", f"{L:.3f}", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "19", "-g", str(media.FPS * 2), "-pix_fmt", "yuv420p", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if kind else subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    err: list[bytes] = []
    reader = threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)
    reader.start()
    try:
        if kind:
            field = _Particles(kind, L, seed)
            try:
                for k in range(int(round(L * PARTICLE_FPS))):
                    proc.stdin.write(field.frame(k / PARTICLE_FPS).tobytes())
            except BrokenPipeError:
                pass
            finally:
                proc.stdin.close()
        rc = proc.wait()
        reader.join(timeout=5)
        if rc != 0:
            raise media.MediaError("Sinematik işleme başarısız:\n" + (err[0] if err else b"").decode(
                errors="replace")[-1500:])
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return out


def ai_scene_prompt(scene_text: str, people: bool = True) -> str:
    who = ("a loving couple seen softly from behind or in gentle silhouette, " if people else "")
    return (f"{scene_text}, {who}cinematic film still, warm golden light, soft depth of field, cozy and romantic "
            "atmosphere, highly detailed, photorealistic, 35mm film, no text")
