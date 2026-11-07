"""Görsel üretimi (Stability AI) ve küçük resim (thumbnail) hazırlama.

STABILITY_API_KEY yoksa veya API hata verirse, prosedürel bir "bokeh"
arka plan üretilir; böylece hat hiçbir zaman görsel yüzünden durmaz.
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import CONFIG

log = logging.getLogger(__name__)

STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)


def generate_image(prompt: str, out: Path, aspect: str = "16:9", seed: int | None = None,
                   fallback: bool = True) -> Path | None:
    """fallback=False: Stability yoksa/hata verirse None döner (prosedürel görsele geçmez)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.stability_api_key:
        try:
            data = {"prompt": prompt, "aspect_ratio": aspect, "output_format": "png",
                    "negative_prompt": "text, letters, watermark, logo, signature, blurry, deformed"}
            if seed is not None:
                data["seed"] = str(seed)
            resp = requests.post(
                STABILITY_URL,
                headers={"Authorization": f"Bearer {CONFIG.stability_api_key}", "Accept": "image/*"},
                files={"none": ""},
                data=data,
                timeout=180,
            )
            if resp.status_code == 200:
                out.write_bytes(resp.content)
                return out
            log.warning("Stability %s: %s — prosedürel görsele geçiliyor", resp.status_code, resp.text[:200])
        except requests.RequestException as e:
            log.warning("Stability hatası: %s — prosedürel görsele geçiliyor", e)
    if not fallback:
        return None
    w, h = (1920, 1080) if aspect == "16:9" else (1080, 1920)
    return procedural_image(out, (w, h), seed)


def procedural_image(out: Path, size: tuple[int, int], seed: int | None = None) -> Path:
    rng = random.Random(seed)
    w, h = size
    palettes = [
        ((20, 24, 48), (88, 56, 120), (255, 170, 120)),
        ((12, 32, 40), (40, 96, 110), (250, 210, 150)),
        ((30, 18, 40), (150, 60, 110), (255, 200, 140)),
        ((14, 22, 30), (60, 80, 120), (180, 220, 255)),
    ]
    top, mid, glow = rng.choice(palettes)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / h
        a, b, k = (top, mid, t * 2) if t < 0.5 else (mid, tuple(int(c * 0.6) for c in top), (t - 0.5) * 2)
        row = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
        for x in range(w):
            px[x, y] = row
    bokeh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(bokeh)
    for _ in range(70):
        r = rng.randint(w // 80, w // 14)
        x, y = rng.randint(0, w), rng.randint(0, h)
        col = tuple(min(255, c + rng.randint(-30, 30)) for c in glow)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, rng.randint(25, 90)))
    bokeh = bokeh.filter(ImageFilter.GaussianBlur(radius=w // 120))
    img = Image.alpha_composite(img.convert("RGBA"), bokeh).convert("RGB")
    img.save(out)
    return out


def vertical_from(image: Path, out: Path) -> Path:
    """Yatay görselin ortasından 9:16 kesit al (Shorts için)."""
    img = Image.open(image).convert("RGB")
    w, h = img.size
    target_w = int(h * 9 / 16)
    left = max(0, (w - target_w) // 2)
    img.crop((left, 0, left + target_w, h)).resize((1080, 1920), Image.LANCZOS).save(out)
    return out


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def make_thumbnail(image: Path, out: Path, headline: str, subline: str = "") -> Path:
    """1280x720 JPEG; sol altta büyük kısa başlık + ince alt yazı."""
    img = Image.open(image).convert("RGB").resize((1280, 720), Image.LANCZOS)
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(320):  # alttan yukarı koyulaşan gradyan, yazı okunurluğu için
        sd.line([(0, 720 - i), (1280, 720 - i)], fill=(0, 0, 0, int(170 * (1 - i / 320))))
    img = Image.alpha_composite(img.convert("RGBA"), shade)
    draw = ImageDraw.Draw(img)

    headline = headline.upper()[:22]
    size = 120
    font = _font(size)
    while draw.textlength(headline, font=font) > 1180 and size > 50:
        size -= 6
        font = _font(size)
    y = 720 - 70 - size - (60 if subline else 0)
    draw.text((52, y), headline, font=font, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    if subline:
        draw.text((56, y + size + 18), subline[:48], font=_font(44), fill=(255, 225, 170),
                  stroke_width=2, stroke_fill=(0, 0, 0))
    img.convert("RGB").save(out, "JPEG", quality=90)
    return out
