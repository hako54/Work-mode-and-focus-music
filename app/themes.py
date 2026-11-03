"""Parça temaları: müziğin ilhamı, başlıkların sahnesi ve kolaj görüntülerinin arama kelimeleri.

Her yeni parça bir tema alır (ör. sonbahar). Müzik prompt'u o temanın havasını anlatır,
Claude başlığı o sahneye göre yazar, video da o temadaki kısa klip ve fotoğraflardan
oluşan bir kolajla hazırlanır. Uzun derlemelerde ise şömine döngüsü kullanılır.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    label: str                       # Telegram'da görünen ad
    music_hint: str                  # müzik prompt'una eklenen ilham
    scene: str                       # başlık/açıklama için sahne
    video_queries: tuple[str, ...]   # stok video aramaları
    photo_queries: tuple[str, ...]   # stok fotoğraf aramaları
    emoji: str


THEMES: tuple[Theme, ...] = (
    Theme("seaside", "Deniz kenarı",
          "the calm rhythm of slow waves on a quiet shore at sunset",
          "a quiet beach at sunset with slow gentle waves and warm golden light",
          ("calm sea waves sunset", "ocean waves beach slow motion", "seashore golden hour"),
          ("beach sunset", "calm sea horizon", "seashells sand"), "🌊"),
    Theme("autumn", "Sonbahar",
          "a slow autumn afternoon with golden leaves softly falling",
          "a golden autumn park with falling leaves and soft afternoon light",
          ("autumn leaves falling", "autumn forest path", "golden autumn trees"),
          ("autumn leaves", "autumn park bench", "maple leaves"), "🍂"),
    Theme("forest", "Orman",
          "a peaceful misty forest with soft sunlight through the trees",
          "a peaceful misty forest with sunbeams through tall trees",
          ("misty forest", "sunlight through trees forest", "forest stream"),
          ("misty forest", "forest sunbeams", "moss forest"), "🌲"),
    Theme("rain", "Yağmur",
          "gentle rain on a window on a cozy evening",
          "gentle rain on a window with warm lights blurred outside",
          ("rain on window", "raindrops on leaves", "rainy street night lights"),
          ("rain window", "raindrops glass", "rainy night city"), "🌧"),
    Theme("winter", "Kış",
          "soft snow falling on a silent winter night",
          "soft snow falling over a quiet winter landscape at night",
          ("snow falling night", "snowy forest", "winter cabin snow"),
          ("snowy trees", "winter cabin lights", "snowflakes"), "❄️"),
    Theme("sunset", "Gün batımı",
          "a warm golden sunset over open fields",
          "a warm golden sunset over open fields and soft clouds",
          ("golden hour field", "sunset clouds timelapse", "sunset over lake"),
          ("golden hour field", "sunset sky", "sunset silhouette couple"), "🌅"),
    Theme("flowers", "Çiçek bahçesi",
          "a blooming rose garden swaying in a light spring breeze",
          "a blooming rose garden in soft spring light",
          ("rose garden", "flower field breeze", "cherry blossom"),
          ("red roses", "flower field", "cherry blossom"), "🌹"),
    Theme("night_sky", "Yıldızlı gece",
          "a starry night sky and soft moonlight",
          "a starry night sky with soft moonlight over calm water",
          ("starry night sky timelapse", "moon clouds night", "night sky stars"),
          ("starry sky", "full moon", "milky way"), "🌙"),
    Theme("lake", "Göl",
          "a calm lake at dawn with soft mist on the water",
          "a calm mountain lake at dawn with mist on still water",
          ("calm lake morning mist", "mountain lake reflection", "lake sunrise"),
          ("lake reflection", "misty lake", "wooden dock lake"), "🏞"),
    Theme("candlelight", "Mum ışığı",
          "an intimate candlelit evening for two",
          "an intimate candlelit room with roses and warm soft light",
          ("candle flame close up", "romantic candles dinner", "candles bokeh"),
          ("candles roses", "candlelight dinner", "candle flame"), "🕯"),
)

THEME_BY_KEY = {t.key: t for t in THEMES}

# Başlıklarda kullanılan İngilizce adlar
EN_LABEL = {"seaside": "Seaside", "autumn": "Autumn", "forest": "Forest", "rain": "Rainy Day",
            "winter": "Winter", "sunset": "Sunset", "flowers": "Rose Garden", "night_sky": "Starry Night",
            "lake": "Lakeside", "candlelight": "Candlelight"}

# Stillere uygun temalar (seçimde öncelikli; geri kalanlar da arada çıkar).
STYLE_THEMES: dict[str, tuple[str, ...]] = {
    "romantic_solo_piano": ("sunset", "seaside", "autumn", "flowers"),
    "spa_massage_piano": ("lake", "forest", "candlelight", "flowers"),
    "dreamy_ambient_love": ("night_sky", "lake", "winter"),
    "piano_strings_love": ("sunset", "flowers", "seaside"),
    "moonlight_piano": ("night_sky", "seaside", "lake"),
    "piano_cello_romance": ("autumn", "forest", "candlelight"),
    "candlelight_jazz_piano": ("candlelight", "rain", "night_sky"),
    "rainy_romance_piano": ("rain", "autumn", "winter"),
    "classical_romance_piano": ("autumn", "flowers", "lake"),
    "wedding_piano": ("flowers", "sunset", "seaside"),
    "fireside_love_ballad": ("autumn", "winter", "forest", "rain"),
    "romantic_sax_lounge": ("candlelight", "night_sky", "rain"),
    "acoustic_love_guitar": ("seaside", "sunset", "flowers", "lake"),
}


ALIASES = {"deniz": "seaside", "sahil": "seaside", "plaj": "seaside", "kar": "winter", "kis": "winter",
           "kış": "winter", "snow": "winter", "orman": "forest", "yagmur": "rain", "yağmur": "rain",
           "sonbahar": "autumn", "fall": "autumn", "gunbatimi": "sunset", "günbatımı": "sunset", "gun": "sunset",
           "gün": "sunset", "cicek": "flowers", "çiçek": "flowers", "gul": "flowers", "gül": "flowers",
           "gece": "night_sky", "yildiz": "night_sky", "yıldız": "night_sky", "ay": "night_sky", "moon": "night_sky",
           "gol": "lake", "göl": "lake", "mum": "candlelight", "candle": "candlelight"}


@dataclass(frozen=True)
class Scene:
    queries: tuple[str, ...]   # tek sahneli video için stok video aramaları (önce ilki denenir)
    title_place: str           # başlıkta: "by the Fire", "on a Rainy Night"
    ambience: str              # başlıkta: "Cozy Night Ambience"
    text: str                  # Claude'a verilen sahne tarifi


# Tek sahneli videolar: tema başına sıcak, sinematik tek bir mekân.
SCENES: dict[str, Scene] = {
    "seaside": Scene(("beach house terrace sunset", "seaside terrace evening", "beach sunset waves"),
                     "by the Sea", "Seaside Sunset Ambience",
                     "a quiet seaside terrace at sunset with soft waves and warm lanterns"),
    "autumn": Scene(("cozy fireplace living room", "autumn cabin fireplace", "fireplace night cozy"),
                    "by the Fire", "Cozy Autumn Night Ambience",
                    "a cozy living room by a crackling fireplace on an autumn night, armchair and warm lamps"),
    "forest": Scene(("forest cabin fireplace", "cabin in the woods night", "cozy cabin interior"),
                    "in a Forest Cabin", "Cozy Cabin Ambience",
                    "a warm wooden cabin in the forest at night with a glowing fireplace"),
    "rain": Scene(("rain window cozy room night", "rain on window night", "rainy night window lamp"),
                  "on a Rainy Night", "Rainy Night Ambience",
                  "a cozy room on a rainy night, raindrops on the window and soft lamp light"),
    "winter": Scene(("cabin fireplace snow window", "snowy night cabin", "winter fireplace cozy"),
                    "on a Snowy Night", "Winter Cabin Ambience",
                    "a warm cabin with a fireplace while snow falls softly outside the window"),
    "sunset": Scene(("sunset terrace wine", "golden hour balcony", "sunset view terrace"),
                    "at Sunset", "Golden Hour Ambience",
                    "a balcony at golden hour with two glasses of wine and a warm sunset"),
    "flowers": Scene(("garden terrace candles evening", "rose garden evening", "romantic garden lights"),
                     "in the Rose Garden", "Romantic Garden Ambience",
                     "a rose garden terrace in the evening with candles and string lights"),
    "night_sky": Scene(("balcony night city lights", "night sky stars timelapse", "moonlight night window"),
                       "Under the Stars", "Starry Night Ambience",
                       "a quiet balcony under a starry night sky with soft moonlight"),
    "lake": Scene(("lake house dock sunset", "lake cabin evening", "calm lake sunset"),
                  "by the Lake", "Lakeside Evening Ambience",
                  "a wooden lake house dock at dusk with calm water and soft lights"),
    "candlelight": Scene(("candlelight dinner romantic", "candles dinner table night", "romantic candles"),
                         "by Candlelight", "Candlelit Dinner Ambience",
                         "an intimate candlelit dinner table for two with roses and warm soft light"),
}


def find_theme(text: str) -> Theme | None:
    """'autumn', 'sonbahar', 'Sonbahar', 'deniz', 'kar' gibi bir yazıdan temayı bul."""
    t = text.strip().lower()
    if t in ALIASES:
        return THEME_BY_KEY[ALIASES[t]]
    for th in THEMES:
        names = {th.key, th.label.lower(), EN_LABEL[th.key].lower(), th.label.lower().split()[0]}
        if t in names or t.replace("_", " ") in names:
            return th
    return None


def pick_theme(style_key: str, recent: list[str], rng: random.Random | None = None) -> Theme:
    """Stile uygun temayı tercih et; son 2 temayı tekrar etme."""
    rng = rng or random.Random()
    preferred = [THEME_BY_KEY[k] for k in STYLE_THEMES.get(style_key, ()) if k not in recent[:2]]
    others = [t for t in THEMES if t.key not in recent[:2] and t not in preferred]
    if preferred and (not others or rng.random() < 0.75):
        return rng.choice(preferred)
    return rng.choice(others or list(THEMES))
