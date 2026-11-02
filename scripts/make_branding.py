"""YouTube'a birebir uyan kanal görselleri (kırpma gerektirmez).

- banner.png   2560x1440  — tüm yazı ve önemli öğeler YouTube'un 1546x423 "her cihazda görünen" alanında
- profile.png  800x800    — amblem dairesel kırpma alanının içinde, kenarlarda boşluk
- watermark.png 150x150   — video filigranı (şeffaf)

Kullanım:  python scripts/make_branding.py ["Kanal Adı"]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "branding"
SERIF_ITALIC = "/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf"
SANS = next((p for p in ("/usr/share/fonts/opentype/inter/Inter-Light.otf",
                         "/usr/share/fonts/opentype/inter/Inter-Regular.otf")
             if Path(p).exists()), "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

GOLD = (236, 196, 128)
GOLD_LIGHT = (255, 232, 180)
CREAM = (255, 240, 222)
ROSE = (176, 22, 48)
SAFE_W, SAFE_H = 1546, 423  # YouTube banner: tüm cihazlarda görünen alan


def gradient_bg(w: int, h: int, cx: float, cy: float) -> Image.Image:
    """Ortası sıcak bordo, kenarlara doğru gece mavisine/siyaha inen radyal gradyan."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - cx) / (w * 0.62), (yy - cy) / (h * 0.62))
    r = np.clip(r, 0, 1)[..., None]
    inner = np.array([92, 18, 38], np.float32)
    mid = np.array([38, 10, 30], np.float32)
    outer = np.array([10, 8, 22], np.float32)
    col = np.where(r < 0.5, inner + (mid - inner) * (r / 0.5), mid + (outer - mid) * ((r - 0.5) / 0.5))
    return Image.fromarray(col.astype(np.uint8), "RGB")


def bokeh(img: Image.Image, rng: random.Random, n: int, box: tuple[int, int, int, int], rmin: int, rmax: int,
          blur: float) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    for _ in range(n):
        r = rng.randint(rmin, rmax)
        x, y = rng.randint(x0, x1), rng.randint(y0, y1)
        warm = rng.choice([(255, 190, 120), (255, 150, 140), (255, 210, 160), (240, 120, 120)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*warm, rng.randint(18, 60)))
    return Image.alpha_composite(img.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(blur)))


def petal(size: int, angle: float, rng: random.Random) -> Image.Image:
    """Gül yaprağı: geniş, üstü hafif çentikli (kalp benzeri), kenarları koyu, ortası kadifemsi."""
    s = size * 2
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    u = (xx - s / 2) / (size * 0.62)
    v = (yy - s / 2) / (size * 0.56)
    # kalp benzeri yaprak: alttan yuvarlak, üstte iki lob
    shape = (u ** 2 + (v * 1.08 - np.sqrt(np.abs(u)) * 0.45) ** 2)
    inside = np.clip((1.0 - shape) / 0.06, 0, 1)
    depth = np.clip(1 - shape, 0, 1)
    shade = 0.45 + 0.55 * depth ** 0.6
    sheen = np.exp(-(((u + 0.25) ** 2) / 0.08 + ((v + 0.25) ** 2) / 0.12)) * 0.35
    r = np.clip(ROSE[0] * shade + 255 * sheen * 0.6, 0, 255)
    g = np.clip(ROSE[1] * shade + 120 * sheen * 0.4, 0, 255)
    b = np.clip(ROSE[2] * shade + 140 * sheen * 0.4, 0, 255)
    im = Image.fromarray(np.dstack([r, g, b, inside * 255]).astype(np.uint8), "RGBA")
    return im.rotate(angle, resample=Image.BICUBIC, expand=False).filter(ImageFilter.GaussianBlur(0.7))


def paste_petal(img: Image.Image, x: int, y: int, size: int, angle: float, rng: random.Random,
                shadow: bool = True) -> Image.Image:
    p = petal(size, angle, rng)
    if shadow:
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
        sh.putalpha(p.getchannel("A").point(lambda v: v * 0.55))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size / 8)), (x - p.width // 2 + 6, y - p.height // 2 + 10))
    img.alpha_composite(p, (x - p.width // 2, y - p.height // 2))
    return img


def piano_keys(width: int, height: int, white_w: int, fade: bool = True) -> Image.Image:
    """Perspektifsiz, önden fildişi tuş dizisi; yanlara doğru şeffaflaşır."""
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    n = width // white_w + 1
    for i in range(n):
        x = i * white_w
        d.rounded_rectangle((x + 1, 0, x + white_w - 2, height), radius=max(2, white_w // 10),
                            fill=(246, 236, 218, 255))
        d.line((x + 1, height - 6, x + white_w - 2, height - 6), fill=(214, 200, 178, 255), width=4)
    pattern = [1, 1, 0, 1, 1, 1, 0]  # C# D# - F# G# A# -
    bw, bh = int(white_w * 0.6), int(height * 0.6)
    for i in range(n):
        if pattern[i % 7]:
            x = (i + 1) * white_w - bw // 2
            d.rounded_rectangle((x, 0, x + bw, bh), radius=max(2, bw // 8), fill=(22, 14, 18, 255))
            d.line((x + bw * 0.25, 4, x + bw * 0.25, bh - 10), fill=(70, 60, 64, 255), width=2)
    # mum ışığı: üstten sıcak ton, alta doğru gölge
    shade = np.linspace(0.75, 1.0, height)[:, None, None]
    arr = np.asarray(im).astype(np.float32)
    arr[..., :3] *= shade
    arr[..., 0] = np.minimum(255, arr[..., 0] * 1.04)
    if fade:
        xs = np.linspace(-1, 1, width)
        alpha = np.clip((1 - np.abs(xs)) / 0.35, 0, 1)
        arr[..., 3] *= alpha[None, :]
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def gold_text(img: Image.Image, xy: tuple[float, float], text: str, f: ImageFont.FreeTypeFont,
              glow: float = 16) -> Image.Image:
    """Dikey altın gradyanlı, hafif parıltılı yazı."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    bbox = mask.getbbox() or (0, 0, 1, 1)
    grad = np.zeros((img.height, img.width, 3), np.float32)
    t = np.clip((np.arange(img.height) - bbox[1]) / max(1, bbox[3] - bbox[1]), 0, 1)[:, None]
    top, bottom = np.array(GOLD_LIGHT, np.float32), np.array((196, 142, 74), np.float32)
    grad[:] = (top + (bottom - top) * t)[:, None, :]  # t: (h, 1) -> (h, 1, 3)
    gold = Image.fromarray(grad.astype(np.uint8), "RGB").convert("RGBA")
    gold.putalpha(mask)
    halo = Image.new("RGBA", img.size, (*GOLD, 0))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: int(v * 0.6)))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.7)))
    img = Image.alpha_composite(img, shadow.transform(img.size, Image.AFFINE, (1, 0, -3, 0, 1, -5)))
    img = Image.alpha_composite(img, halo)
    return Image.alpha_composite(img, gold)


def heart(cx: float, cy: float, s: float, steps: int = 200) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy - y * s))
    return pts


def ring(size: int, thickness: float, angle: float) -> Image.Image:
    """Eğik duran altın alyans (elips halka, ışıklı)."""
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    rx, ry = s * 0.42, s * 0.42 * 0.42
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    u, v = (xx - s / 2) / rx, (yy - s / 2) / ry
    rr = np.hypot(u, v)
    band = np.clip(1 - np.abs(rr - 1) / (thickness / rx), 0, 1)
    light = 0.55 + 0.45 * np.clip(-v / (np.hypot(u, v) + 1e-6), -1, 1)       # üst kenar parlak
    spec = np.exp(-((np.arctan2(v, u) + 2.2) ** 2) / 0.05) * 0.9             # parlama noktası
    r = np.clip(200 * light + 255 * spec, 0, 255)
    g = np.clip(150 * light + 235 * spec, 0, 255)
    b = np.clip(70 * light + 190 * spec, 0, 255)
    arr = np.dstack([r, g, b, band * 255]).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA").filter(ImageFilter.GaussianBlur(0.8))
    return im.rotate(angle, resample=Image.BICUBIC)


def make_banner(name: str) -> Path:
    W, H = 2560, 1440
    rng = random.Random(21)
    img = gradient_bg(W, H, W / 2, H / 2).convert("RGBA")
    img = bokeh(img, rng, 60, (0, 0, W, H), 30, 120, 30)
    img = bokeh(img, rng, 40, (W // 2 - 900, H // 2 - 260, W // 2 + 900, H // 2 + 260), 10, 40, 8)

    safe = (W // 2 - SAFE_W // 2, H // 2 - SAFE_H // 2, W // 2 + SAFE_W // 2, H // 2 + SAFE_H // 2)
    keys = piano_keys(SAFE_W + 300, 120, 58)
    img.alpha_composite(keys, (W // 2 - keys.width // 2, safe[3] - 118))

    title_f = ImageFont.truetype(SERIF_ITALIC, 168)
    d = ImageDraw.Draw(img)
    tw = d.textlength(name, font=title_f)
    while tw > SAFE_W - 120:
        title_f = ImageFont.truetype(SERIF_ITALIC, title_f.size - 6)
        tw = d.textlength(name, font=title_f)
    ty = safe[1] + 10
    img = gold_text(img, ((W - tw) / 2, ty), name, title_f)

    d = ImageDraw.Draw(img)
    ly = ty + title_f.size + 28
    d.line((W / 2 - 300, ly, W / 2 - 34, ly), fill=(*GOLD, 200), width=3)
    d.line((W / 2 + 34, ly, W / 2 + 300, ly), fill=(*GOLD, 200), width=3)
    d.polygon(heart(W / 2, ly + 2, 1.25), fill=(*GOLD, 235))
    sub = ImageFont.truetype(SANS, 40)
    tag = "SOFT ROMANTIC PIANO   ·   1–3+ HOUR MIXES   ·   NEW EVERY 2 DAYS"
    d.text(((W - d.textlength(tag, font=sub)) / 2, ly + 28), tag, font=sub, fill=(*CREAM, 235))

    for (x, y, s, a) in [(safe[0] + 40, safe[3] - 150, 70, 30), (safe[0] + 120, safe[3] - 110, 52, -40),
                         (safe[2] - 70, safe[3] - 140, 64, -25), (safe[2] - 150, safe[3] - 100, 48, 55),
                         (W // 2 + 420, safe[3] - 108, 40, 10), (W // 2 - 460, safe[3] - 112, 44, -60)]:
        img = paste_petal(img, x, y, s, a, rng)
    out = OUT / "banner.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def make_profile(name: str) -> Path:
    """Küçük boyutta bile okunur amblem: altın kalp + monogram + piyano tuşları, tamamı daire içinde."""
    S = 800
    rng = random.Random(5)
    img = gradient_bg(S, S, S / 2, S / 2).convert("RGBA")
    img = bokeh(img, rng, 18, (120, 120, 680, 680), 10, 40, 10)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((170, 150, 630, 610), fill=(255, 170, 110, 60))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(80)))

    # Altın kalp (kalın, gradyanlı) — dairenin içinde, kenarlarda en az %12 boşluk
    hp = heart(S / 2, S / 2 - 20, 15.0, 400)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).line(hp + hp[:1], fill=255, width=22, joint="curve")
    t = np.linspace(0, 1, S)[:, None, None]
    grad = (np.array(GOLD_LIGHT) + (np.array((190, 136, 70)) - np.array(GOLD_LIGHT)) * t) * np.ones((1, S, 1))
    gold = Image.fromarray(grad.astype(np.uint8), "RGB").convert("RGBA")
    gold.putalpha(mask)
    halo = Image.new("RGBA", (S, S), (*GOLD, 0))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55)))
    img = Image.alpha_composite(Image.alpha_composite(img, halo), gold)

    # Piyano tuşları kalbin içinde, alt kısımda
    keys = piano_keys(330, 95, 47)
    hm = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hm).polygon(heart(S / 2, S / 2 - 20, 13.6, 400), fill=255)
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    layer.alpha_composite(keys, (S // 2 - keys.width // 2, 420))
    layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.getchannel("A")), np.asarray(hm))))
    img = Image.alpha_composite(img, layer)

    initials = "".join(w[0] for w in name.split() if w[0].isalpha())[:2].upper() or "ER"
    f = ImageFont.truetype(SERIF_ITALIC, 230)
    d = ImageDraw.Draw(img)
    tw = d.textlength(initials, font=f)
    img = gold_text(img, ((S - tw) / 2 - 6, 175), initials, f, glow=12)
    for (x, y, sz, a) in [(205, 610, 70, 25), (600, 600, 62, -30)]:
        img = paste_petal(img, x, y, sz, a, rng)
    out = OUT / "profile.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def make_watermark() -> Path:
    S = 300
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hp = heart(S / 2, S / 2 + 8, 6.2)
    d.line(hp + hp[:1], fill=(*CREAM, 235), width=9, joint="curve")
    out = OUT / "watermark.png"
    img.resize((150, 150), Image.LANCZOS).save(out)
    return out

# ----------------------------------------------------------------------------- banner alternatifleri
TAG = "SOFT ROMANTIC PIANO   ·   1–3+ HOUR MIXES   ·   NEW EVERY 2 DAYS"
RELAX_TAG = "SOFT ROMANTIC PIANO   ·   RELAXING   ·   CALM   ·   SWEET DREAMS"


def _safe(W: int, H: int) -> tuple[int, int, int, int]:
    return (W // 2 - SAFE_W // 2, H // 2 - SAFE_H // 2, W // 2 + SAFE_W // 2, H // 2 + SAFE_H // 2)


def _fit_font(d: ImageDraw.ImageDraw, text: str, path: str, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    while d.textlength(text, font=f) > max_w and size > 40:
        size -= 6
        f = ImageFont.truetype(path, size)
    return f


def solid_text(img: Image.Image, xy, text: str, f, color, glow_color=None, glow: float = 14) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    if glow_color:
        halo = Image.new("RGBA", img.size, (*glow_color, 0))
        halo.putalpha(mask.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: int(v * 0.6)))
        img = Image.alpha_composite(img, halo)
    layer = Image.new("RGBA", img.size, (*color, 0))
    layer.putalpha(mask)
    return Image.alpha_composite(img, layer)


def title_block(img: Image.Image, name: str, top: int, style: str = "gold", line=GOLD, tag_color=CREAM,
                size: int = 168, tag: str = TAG) -> Image.Image:
    """Başlık + kalpli ayraç + alt yazı; hepsi güvenli alanın genişliği içinde ortalanır."""
    W = img.width
    d = ImageDraw.Draw(img)
    f = _fit_font(d, name, SERIF_ITALIC, size, SAFE_W - 120)
    tw = d.textlength(name, font=f)
    if style == "gold":
        img = gold_text(img, ((W - tw) / 2, top), name, f)
    else:
        img = solid_text(img, ((W - tw) / 2, top), name, f, style, glow_color=None)
    d = ImageDraw.Draw(img)
    ly = top + f.size + 28
    d.line((W / 2 - 300, ly, W / 2 - 34, ly), fill=(*line, 210), width=3)
    d.line((W / 2 + 34, ly, W / 2 + 300, ly), fill=(*line, 210), width=3)
    d.polygon(heart(W / 2, ly + 2, 1.25), fill=(*line, 240))
    sub = ImageFont.truetype(SANS, 40)
    d.text(((W - d.textlength(tag, font=sub)) / 2, ly + 28), tag, font=sub, fill=(*tag_color, 240))
    return img


def vertical_gradient(W: int, H: int, stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    t = np.linspace(0, 1, H)
    col = np.zeros((H, 3), np.float32)
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        m = (t >= a) & (t <= b)
        k = ((t[m] - a) / (b - a))[:, None]
        col[m] = np.array(ca) + (np.array(cb) - np.array(ca)) * k
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8), "RGB")


def banner_moonlight(name: str) -> Path:
    """Gece mavisi gökyüzü, yıldızlar, hilal ve ayın sıcak ışığı."""
    W, H = 2560, 1440
    rng = random.Random(8)
    img = vertical_gradient(W, H, [(0, (6, 8, 26)), (0.5, (22, 22, 60)), (0.75, (58, 26, 58)), (1, (20, 8, 20))])
    img = img.convert("RGBA")
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(stars)
    for _ in range(900):
        x, y = rng.randint(0, W), rng.randint(0, H)
        r = rng.choice([1, 1, 1, 2, 2, 3])
        a = rng.randint(80, 255)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 245, 230, a))
    img = Image.alpha_composite(img, stars.filter(ImageFilter.GaussianBlur(0.6)))
    sf = _safe(W, H)
    # hilal: güvenli alanın sağ üst köşesinde
    mx, my, mr = sf[2] + 60, sf[1] - 110, 80  # yazının dışında, sağ üstte (dekor)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((mx - mr * 4, my - mr * 4, mx + mr * 4, my + mr * 4), fill=(255, 220, 170, 50))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(90)))
    moon = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(moon)
    md.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=255)
    md.ellipse((mx - mr + 34, my - mr - 14, mx + mr + 34, my + mr - 14), fill=0)
    layer = Image.new("RGBA", (W, H), (255, 236, 200, 0))
    layer.putalpha(moon.filter(ImageFilter.GaussianBlur(1.2)))
    img = Image.alpha_composite(img, layer)
    # alt kısımda sakin su yansıması gibi yumuşak ışık şeridi
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).ellipse((W / 2 - 900, sf[3] - 60, W / 2 + 900, sf[3] + 120), fill=(255, 190, 150, 45))
    img = Image.alpha_composite(img, band.filter(ImageFilter.GaussianBlur(60)))
    img = title_block(img, name, sf[1] + 90, tag=RELAX_TAG)
    out = OUT / "banner_alternatives" / "banner_B_moonlight.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def banner_blush(name: str) -> Path:
    """Açık, zarif: krem-pudra zemin, bordo yazı, iki yanda gül yaprakları."""
    W, H = 2560, 1440
    rng = random.Random(3)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.clip(np.hypot((xx - W / 2) / W, (yy - H / 2) / H) * 1.6, 0, 1)[..., None]
    c0, c1 = np.array((253, 244, 238), np.float32), np.array((236, 200, 200), np.float32)
    img = Image.fromarray((c0 + (c1 - c0) * r).astype(np.uint8), "RGB").convert("RGBA")
    img = bokeh(img, rng, 50, (0, 0, W, H), 30, 110, 30)
    sf = _safe(W, H)
    wine = (110, 18, 40)
    img = title_block(img, name, sf[1] + 80, style=wine, line=(184, 134, 70), tag_color=(120, 60, 70), size=140)
    for (x, y, sz, a) in [(sf[0] - 60, sf[1] + 120, 84, 30), (sf[0] - 10, sf[1] + 230, 58, -30),
                          (sf[0] - 120, sf[3] - 60, 66, 70), (sf[2] + 60, sf[1] + 110, 80, -20),
                          (sf[2] + 10, sf[1] + 240, 54, 40), (sf[2] + 120, sf[3] - 50, 68, -60),
                          (W // 2 - 520, sf[3] - 30, 40, 15), (W // 2 + 540, sf[3] - 34, 38, -15)]:
        img = paste_petal(img, x, y, sz, a, rng)
    out = OUT / "banner_alternatives" / "banner_C_blush.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def candle(h: int) -> Image.Image:
    """Krem mum + alev + sıcak hale."""
    w = int(h * 0.32)
    S = (w * 12, h * 3)  # halenin bulanıklığı tuval kenarında kesilmesin
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    cx, base = S[0] // 2, S[1] - 10
    glow = Image.new("RGBA", S, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - w * 2.6, base - h - w * 2.6, cx + w * 2.6, base - h + w * 2.2),
                                 fill=(255, 170, 80, 110))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(w)))
    d = ImageDraw.Draw(im)
    body = np.linspace(1.0, 0.7, w)
    for i, k in enumerate(body):
        x = cx - w // 2 + i
        shade = 0.75 + 0.25 * math.sin(math.pi * i / w)
        d.line((x, base - h, x, base), fill=(int(248 * shade), int(232 * shade), int(206 * shade), 255))
    d.ellipse((cx - w // 2, base - h - w * 0.12, cx + w // 2, base - h + w * 0.12), fill=(255, 244, 222, 255))
    d.line((cx, base - h - 2, cx, base - h - w * 0.35), fill=(40, 30, 30, 255), width=3)
    flame = Image.new("RGBA", S, (0, 0, 0, 0))
    fd = ImageDraw.Draw(flame)
    fy = base - h - w * 0.35
    fd.ellipse((cx - w * 0.18, fy - w * 0.9, cx + w * 0.18, fy + w * 0.05), fill=(255, 190, 90, 230))
    fd.ellipse((cx - w * 0.09, fy - w * 0.55, cx + w * 0.09, fy), fill=(255, 250, 220, 255))
    return Image.alpha_composite(im, flame.filter(ImageFilter.GaussianBlur(2.5)))


def banner_candle(name: str) -> Path:
    """Koyu sıcak zemin, iki yanda farklı boylarda mumlar, ortada başlık."""
    W, H = 2560, 1440
    rng = random.Random(12)
    img = gradient_bg(W, H, W / 2, H / 2 + 80).convert("RGBA")
    img = bokeh(img, rng, 50, (0, 0, W, H), 20, 90, 25)
    sf = _safe(W, H)
    for x, ch in [(sf[0] - 60, 300), (sf[0] + 15, 200), (sf[0] - 150, 170),
                  (sf[2] + 60, 300), (sf[2] - 15, 200), (sf[2] + 150, 170)]:
        c = candle(ch)
        img.alpha_composite(c, (x - c.width // 2, sf[3] - c.height + 10))
    img = title_block(img, name, sf[1] + 70, size=128)
    for (x, y, sz, a) in [(W // 2 - 380, sf[3] - 30, 46, 20), (W // 2 + 360, sf[3] - 26, 42, -35),
                          (W // 2 - 40, sf[3] - 18, 34, 60)]:
        img = paste_petal(img, x, y, sz, a, rng)
    out = OUT / "banner_alternatives" / "banner_D_candlelight.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def banner_staff(name: str) -> Path:
    """Bordo zeminde soldan sağa akan altın porte çizgileri ve süzülen notalar."""
    W, H = 2560, 1440
    rng = random.Random(30)
    img = gradient_bg(W, H, W / 2, H / 2).convert("RGBA")
    img = bokeh(img, rng, 45, (0, 0, W, H), 30, 110, 30)
    sf = _safe(W, H)
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    base_y = sf[3] - 52
    xs = np.arange(0, W + 1, 8)
    for k in range(5):
        pts = [(float(x), base_y + k * 16 + 38 * math.sin(x / 260) + 18 * math.sin(x / 97 + 1.3)) for x in xs]
        d.line(pts, fill=(*GOLD, 150), width=2)
    fade = np.clip(1 - np.abs(np.linspace(-1, 1, W)) ** 2.2, 0, 1)
    a = np.asarray(lines.getchannel("A")).astype(np.float32) * fade[None, :]
    lines.putalpha(Image.fromarray(a.astype(np.uint8)))
    img = Image.alpha_composite(img, lines)
    note_f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 64)
    d = ImageDraw.Draw(img)
    for x, sym, sz in [(sf[0] - 120, "♪", 70), (sf[0] + 60, "♫", 62), (W // 2 - 620, "♩", 52),
                       (W // 2 + 600, "♪", 56), (sf[2] - 60, "♫", 66), (sf[2] + 120, "♪", 72)]:
        y = base_y + 38 * math.sin(x / 260) + 18 * math.sin(x / 97 + 1.3) - 30
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sz)
        img = solid_text(img, (x, y), sym, f, GOLD_LIGHT, glow_color=GOLD, glow=10)
    img = title_block(img, name, sf[1] + 20, size=150)
    out = OUT / "banner_alternatives" / "banner_E_melody.png"
    img.convert("RGB").save(out, optimize=True)
    return out


def contact_sheet(paths: list[Path]) -> Path:
    """Tüm banner'ları, telefonda görünen güvenli alan çerçevesiyle tek sayfada göster."""
    tw, th = 1280, 720
    sheet = Image.new("RGB", (tw * 2 + 60, (th + 90) * ((len(paths) + 1) // 2) + 20), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    lab = ImageFont.truetype(SANS, 34)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        x, y = 20 + (i % 2) * (tw + 20), 20 + (i // 2) * (th + 90)
        sheet.paste(im, (x, y))
        sx, sy = SAFE_W / 2560 * tw, SAFE_H / 1440 * th
        d.rectangle((x + (tw - sx) / 2, y + (th - sy) / 2, x + (tw + sx) / 2, y + (th + sy) / 2),
                    outline=(120, 220, 255), width=3)
        d.text((x, y + th + 18), p.stem.replace("banner_", "").replace("_", " "), font=lab, fill=(230, 230, 230))
    out = OUT / "banner_alternatives" / "_overview.jpg"
    sheet.save(out, quality=88)
    return out


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "Evermore Romance Piano"
    OUT.mkdir(exist_ok=True)
    (OUT / "banner_alternatives").mkdir(exist_ok=True)
    a = make_banner(name)
    alt_a = OUT / "banner_alternatives" / "banner_A_rose_keys.png"
    Image.open(a).save(alt_a, optimize=True)
    alts = [alt_a, banner_moonlight(name), banner_blush(name), banner_candle(name), banner_staff(name)]
    Image.open(alts[1]).save(OUT / "banner.png", optimize=True)  # seçilen ana banner: B (moonlight)
    for p in (*alts, make_profile(name), make_watermark(), contact_sheet(alts)):
        im = Image.open(p)
        print(p.relative_to(ROOT), im.size)


if __name__ == "__main__":
    main()
