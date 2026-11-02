"""Kanal görsellerini üret: profil fotoğrafı (800x800) ve banner (2560x1440).

Kullanım:  python scripts/make_branding.py [kanal adı]
Çıktı:     branding/profile.png, branding/banner.png, branding/watermark.png
Kaynak:    assets/fireplace/ içindeki ilk fotoğraf (şömine)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "branding"
SERIF_ITALIC = "/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf"
SERIF_BOLD_ITALIC = "/usr/share/fonts/truetype/crosextra/Caladea-BoldItalic.ttf"
SANS_LIGHT = next((p for p in ("/usr/share/fonts/opentype/inter/Inter-Light.otf",
                               "/usr/share/fonts/truetype/inter/Inter-Light.ttf")
                   if Path(p).exists()), "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
GOLD = (244, 200, 140)
CREAM = (255, 238, 214)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def source_photo() -> Image.Image:
    photos = sorted(p for p in (ROOT / "assets" / "fireplace").iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    return Image.open(photos[0]).convert("RGB")


def crop_box(img: Image.Image, cx: float, cy: float, w_frac: float, aspect: float) -> Image.Image:
    """(cx, cy) merkezli, genişliği w_frac oranında ve verilen en/boy oranında kesit."""
    W, H = img.size
    w = W * w_frac
    h = w / aspect
    if h > H:
        h, w = H, H * aspect
    left = min(max(0, cx * W - w / 2), W - w)
    top = min(max(0, cy * H - h / 2), H - h)
    return img.crop((round(left), round(top), round(left + w), round(top + h)))


def warm_grade(img: Image.Image, dark: float = 0.8) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.15)
    return ImageEnhance.Brightness(img).enhance(dark)


def radial_vignette(size: tuple[int, int], strength: float = 0.85, inner: float = 0.35) -> Image.Image:
    """Merkezden kenara yumuşakça koyulaşan maske (255 = tamamen karartılmış)."""
    import numpy as np
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)  # köşe = 1
    v = np.clip((r - inner * 0.7) / (1 - inner * 0.7), 0, 1) ** 1.4 * strength
    return Image.fromarray((v * 255).astype(np.uint8), "L")


def darken(img: Image.Image, mask: Image.Image) -> Image.Image:
    black = Image.new("RGB", img.size, (8, 4, 2))
    return Image.composite(black, img, mask)


def heart_path(cx: float, cy: float, s: float, steps: int = 400) -> list[tuple[float, float]]:
    import math
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy - y * s))
    return pts


def glow_layer(size: tuple[int, int], draw_fn, color, blur: float, intensity: int = 2) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), color)
    glow = layer.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for _ in range(intensity):
        out = Image.alpha_composite(out, glow)
    return Image.alpha_composite(out, layer)


def centered(draw: ImageDraw.ImageDraw, y: float, text: str, f: ImageFont.FreeTypeFont, width: int, **kw) -> None:
    w = draw.textlength(text, font=f)
    draw.text(((width - w) / 2, y), text, font=f, **kw)


def make_profile(photo: Image.Image, name: str) -> Path:
    S = 800
    bg = crop_box(photo, 0.47, 0.44, 0.42, 1.0).resize((S, S), Image.LANCZOS)
    bg = warm_grade(bg.filter(ImageFilter.GaussianBlur(2)), 0.62)
    bg = darken(bg, radial_vignette((S, S), 0.92, 0.3))
    img = bg.convert("RGBA")

    pts = heart_path(S / 2, S / 2 + 18, 15.5)
    img = Image.alpha_composite(img, glow_layer((S, S), lambda d, c: d.line(pts + pts[:1], fill=c, width=9,
                                                                            joint="curve"), (*GOLD, 255), 14))
    d = ImageDraw.Draw(img)
    initials = "".join(w[0] for w in name.replace("&", " & ").split() if w[0].isalnum()) or "EK"
    mono = f"{initials[0]}&{initials[-1]}" if len(initials) >= 2 else initials
    f = font(SERIF_BOLD_ITALIC, 205)
    w = d.textlength(mono, font=f)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(((S - w) / 2, S / 2 - 120), mono, font=f, fill=(0, 0, 0, 200))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    d.text(((S - w) / 2, S / 2 - 120), mono, font=f, fill=CREAM)
    out = OUT / "profile.png"
    img.convert("RGB").save(out)
    return out


def make_banner(photo: Image.Image, name: str) -> Path:
    W, H = 2560, 1440
    bg = crop_box(photo, 0.5, 0.55, 1.0, W / H).resize((W, H), Image.LANCZOS)
    bg = warm_grade(bg, 0.55)
    # Ortadaki "güvenli alan" (1546x423) yazı için koyulaştırılır; kenarlarda ateş görünür kalır.
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((W / 2 - 900, H / 2 - 300, W / 2 + 900, H / 2 + 300), 300, fill=190)
    bg = darken(bg, mask.filter(ImageFilter.GaussianBlur(160)))
    img = bg.convert("RGBA")

    title = font(SERIF_ITALIC, 190)
    sub = font(SANS_LIGHT, 50)
    small = font(SANS_LIGHT, 38)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    centered(d, H / 2 - 195, name, title, W, fill=(*CREAM, 255))
    centered(d, H / 2 + 60, "ROMANTIC PIANO  ·  CRACKLING FIREPLACE  ·  SPA RELAXATION", sub, W,
             fill=(*GOLD, 255))
    centered(d, H / 2 + 145, "New long mixes every two days  —  1 to 3+ hours of uninterrupted calm", small, W,
             fill=(235, 215, 190, 230))
    glow = layer.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, Image.eval(glow, lambda v: v // 2))
    img = Image.alpha_composite(img, layer)
    d = ImageDraw.Draw(img)
    y = H / 2 + 28
    d.line((W / 2 - 360, y, W / 2 - 40, y), fill=(*GOLD, 160), width=2)
    d.line((W / 2 + 40, y, W / 2 + 360, y), fill=(*GOLD, 160), width=2)
    hp = heart_path(W / 2, y + 2, 1.1, 120)
    d.polygon(hp, fill=(*GOLD, 220))
    out = OUT / "banner.png"
    img.convert("RGB").save(out)
    return out


def make_watermark(name: str) -> Path:
    """Video filigranı (YouTube 'Branding' > Video watermark, 150x150, şeffaf)."""
    S = 300
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pts = heart_path(S / 2, S / 2 + 8, 6.2)
    d = ImageDraw.Draw(img)
    d.line(pts + pts[:1], fill=(*CREAM, 230), width=8, joint="curve")
    out = OUT / "watermark.png"
    img.resize((150, 150), Image.LANCZOS).save(out)
    return out


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "Ember & Keys"
    OUT.mkdir(exist_ok=True)
    photo = source_photo()
    for p in (make_profile(photo, name), make_banner(photo, name), make_watermark(name)):
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
