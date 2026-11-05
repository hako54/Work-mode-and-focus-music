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
          ("golden hour field", "golden sunset clouds slow", "sunset over lake"),
          ("golden hour field", "sunset sky", "sunset silhouette couple"), "🌅"),
    Theme("flowers", "Çiçek bahçesi",
          "a blooming rose garden swaying in a light spring breeze",
          "a blooming rose garden in soft spring light",
          ("rose garden", "flower field breeze", "cherry blossom"),
          ("red roses", "flower field", "cherry blossom"), "🌹"),
    Theme("night_sky", "Yıldızlı gece",
          "a starry night sky and soft moonlight",
          "a starry night sky with soft moonlight over calm water",
          ("calm night sky stars", "moon clouds night", "night sky stars"),
          ("starry sky", "full moon", "milky way"), "🌙"),
    Theme("lake", "Göl",
          "a calm lake at dawn with soft mist on the water",
          "a calm mountain lake at dawn with mist on still water",
          ("calm lake morning mist", "mountain lake reflection", "lake sunrise"),
          ("lake reflection", "misty lake", "wooden dock lake"), "🏞"),
    Theme("fireplace", "Şömine",
          "a warm crackling fireplace on a cozy night at home",
          "a cozy living room by a crackling fireplace at night, armchair, blankets and warm lamps",
          ("cozy fireplace living room", "fireplace burning cozy room", "stone fireplace night"),
          ("cozy fireplace", "fireplace living room", "fireplace armchair"), "🔥"),
    Theme("picnic", "Sonbahar pikniği",
          "a quiet autumn picnic in the forest with golden leaves slowly falling",
          "an autumn picnic in a quiet forest with a blanket, a basket and golden leaves",
          ("autumn picnic forest", "picnic blanket autumn leaves", "autumn park picnic"),
          ("autumn picnic", "picnic basket leaves", "autumn forest blanket"), "🧺"),
    Theme("cafe", "Kafe",
          "a cozy café on a rainy evening, warm lamps and quiet conversations",
          "a cozy café at night with warm lamps, coffee cups and rain on the window",
          ("cozy cafe night", "coffee shop rain window", "cafe interior warm lights"),
          ("cozy cafe", "coffee cup window rain", "cafe lights night"), "☕"),
    Theme("city_night", "Şehir ışıkları",
          "city lights glowing softly at night seen from a quiet apartment",
          "a quiet apartment window at night overlooking glowing city lights",
          ("city lights night window", "city lights night slow", "night city bokeh"),
          ("city night lights", "apartment window city night", "night skyline"), "🌃"),
    Theme("candlelight", "Mum ışığı",
          "an intimate candlelit evening for two",
          "an intimate candlelit room with roses and warm soft light",
          ("candle flame close up", "romantic candles dinner", "candles bokeh"),
          ("candles roses", "candlelight dinner", "candle flame"), "🕯"),
)

THEME_BY_KEY = {t.key: t for t in THEMES}

# Başlıklarda kullanılan İngilizce adlar
EN_LABEL = {"fireplace": "Fireplace", "picnic": "Autumn Picnic", "cafe": "Café", "city_night": "City Lights", "seaside": "Seaside", "autumn": "Autumn", "forest": "Forest", "rain": "Rainy Day",
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
    "fireside_love_ballad": ("fireplace", "autumn", "winter", "forest", "rain"),
    "romantic_sax_lounge": ("candlelight", "night_sky", "rain"),
    "acoustic_love_guitar": ("seaside", "sunset", "flowers", "lake", "picnic"),
    "cozy_jazz_cafe": ("cafe", "city_night", "rain", "fireplace"),
    "rainy_jazz_night": ("rain", "cafe", "city_night"),
    "bossa_nova_evening": ("seaside", "sunset", "cafe"),
    "deep_sleep_ambient": ("night_sky", "lake", "winter"),
    "sleep_piano_rain": ("rain", "winter", "night_sky", "fireplace"),
    "nature_relax_piano": ("forest", "lake", "seaside"),
    "healing_meditation": ("lake", "forest", "flowers"),
}


ALIASES = {"şömine": "fireplace", "somine": "fireplace", "fireplace": "fireplace", "ates": "fireplace",
           "ateş": "fireplace", "piknik": "picnic", "picnic": "picnic", "kafe": "cafe", "cafe": "cafe", "kahve": "cafe", "sehir": "city_night", "şehir": "city_night",
           "city": "city_night", "deniz": "seaside", "sahil": "seaside", "plaj": "seaside", "kar": "winter", "kis": "winter",
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
    "autumn": Scene(("cozy fireplace living room", "fireplace armchair cozy night", "autumn cabin fireplace"),
                    "by the Fire", "Cozy Autumn Night Ambience",
                    "a cozy living room by a crackling fireplace on an autumn night, armchair and warm lamps"),
    "forest": Scene(("cozy cabin in the woods", "forest cabin fireplace", "autumn forest path calm"),
                    "in a Forest Cabin", "Cozy Cabin Ambience",
                    "a warm wooden cabin in the forest at night with a glowing fireplace"),
    "rain": Scene(("rain window cozy room", "rain on window night lamp", "rainy window candle"),
                  "on a Rainy Night", "Rainy Night Ambience",
                  "a cozy room on a rainy night, raindrops on the window and soft lamp light"),
    "winter": Scene(("snowy cabin window fireplace", "snow falling cozy cabin", "winter fireplace snow outside"),
                    "on a Snowy Night", "Winter Cabin Ambience",
                    "a warm cabin with a fireplace while snow falls softly outside the window"),
    "sunset": Scene(("sunset terrace wine", "golden hour balcony", "sunset view terrace"),
                    "at Sunset", "Golden Hour Ambience",
                    "a balcony at golden hour with two glasses of wine and a warm sunset"),
    "flowers": Scene(("garden terrace candles evening", "rose garden evening", "romantic garden lights"),
                     "in the Rose Garden", "Romantic Garden Ambience",
                     "a rose garden terrace in the evening with candles and string lights"),
    "night_sky": Scene(("balcony night city lights", "calm starry night", "moonlight night window"),
                       "Under the Stars", "Starry Night Ambience",
                       "a quiet balcony under a starry night sky with soft moonlight"),
    "lake": Scene(("lake house dock sunset", "lake cabin evening", "calm lake sunset"),
                  "by the Lake", "Lakeside Evening Ambience",
                  "a wooden lake house dock at dusk with calm water and soft lights"),
    "fireplace": Scene(("cozy fireplace living room", "fireplace armchair cozy night", "stone fireplace burning"),
                       "by the Fire", "Cozy Fireplace Ambience",
                       "a cozy living room by a crackling fireplace at night, an armchair, blankets and warm lamps"),
    "picnic": Scene(("autumn picnic forest", "picnic blanket autumn leaves", "autumn forest picnic basket"),
                    "at an Autumn Picnic", "Autumn Forest Ambience",
                    "a quiet autumn picnic in the forest, a blanket, a basket and golden leaves slowly falling"),
    "cafe": Scene(("cozy cafe night rain", "coffee shop interior evening", "cafe window rain night"),
                  "in a Cozy Café", "Rainy Café Ambience",
                  "a cozy café at night with warm lamps, a cup of coffee and rain on the window"),
    "city_night": Scene(("city lights night window apartment", "night city view window", "city skyline night"),
                        "Under the City Lights", "Late Night City Ambience",
                        "a quiet apartment by a big window at night, city lights glowing below"),
    "candlelight": Scene(("candlelight dinner romantic", "candles dinner table night", "romantic candles"),
                         "by Candlelight", "Candlelit Dinner Ambience",
                         "an intimate candlelit dinner table for two with roses and warm soft light"),
}


TR_SUFFIXES = ("ndaki", "ndeki", "daki", "deki", "taki", "teki", "nda", "nde", "lı", "li", "lu", "lü", "da", "de",
               "ta", "te", "ya", "ye", "a", "e", "ı", "i", "u", "ü")


def _variants(text: str) -> list[str]:
    """Türkçe eklerini atarak aday kökler: 'şömineli' -> 'şömine', 'ormanda' -> 'orman', 'karlı' -> 'kar'."""
    t = text.strip().lower().replace("i̇", "i")
    out = [t]
    for suf in TR_SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 2:
            out.append(t[: -len(suf)])
    return out


# Geriye oynatılınca doğal görünen sahneler (bumerang döngüsü için). Yağmur, kar, düşen yapraklar, ateş ve
# dalgalar geriye akınca fark edilir; onlarda aynı mekândan birkaç çekim art arda kullanılır.
REVERSIBLE = frozenset({"lake", "night_sky", "city_night", "sunset", "candlelight", "flowers"})


# Kapak fotoğrafı aramaları: temaya uygun, insan içeren (çift / kadın), sıcak ve romantik — müstehcen değil.
PEOPLE_QUERIES: dict[str, tuple[str, ...]] = {
    "fireplace": ("couple by fireplace blanket", "woman reading by fireplace", "couple cozy fireplace night"),
    "autumn": ("couple autumn park walk", "woman autumn leaves smiling", "couple autumn forest"),
    "winter": ("couple snow winter romantic", "woman cozy window snow", "couple winter cabin"),
    "rain": ("woman rain window coffee", "couple umbrella rain", "woman looking at rain window"),
    "cafe": ("woman coffee cafe window", "couple cafe date", "woman cafe rainy day"),
    "city_night": ("couple city lights night", "woman window city night", "couple rooftop night"),
    "seaside": ("couple beach sunset", "woman beach sunset dress", "couple walking beach"),
    "sunset": ("couple sunset silhouette", "woman golden hour field", "couple sunset hug"),
    "flowers": ("woman rose garden", "couple flower field", "woman holding roses"),
    "night_sky": ("couple under stars", "woman moonlight window", "couple night sky"),
    "lake": ("couple lake dock sunset", "woman lake sunrise", "couple lake romantic"),
    "candlelight": ("couple candlelight dinner", "woman candles romantic", "couple wine candles"),
    "picnic": ("couple autumn picnic", "woman picnic autumn forest", "couple picnic blanket"),
    "forest": ("couple forest walk", "woman forest sunlight", "couple cabin woods"),
    "seaside_relax": ("woman relaxing beach", "woman meditation sea", "woman yoga beach"),
}
SERIES_PEOPLE: dict[str, tuple[str, ...]] = {
    "sleep": ("woman sleeping peacefully bed", "cozy bed night window", "woman sleeping blanket"),
    "relax": ("woman relaxing spa", "woman meditating nature", "woman calm lake"),
    "jazz": ("woman coffee cafe window", "couple jazz bar", "woman listening music cozy"),
}


def people_queries(theme_key: str | None, series_key: str | None = None) -> tuple[str, ...]:
    """Kapak için insan içeren aramalar: önce temaya, sonra seriye göre."""
    out = list(PEOPLE_QUERIES.get(theme_key or "", ()))
    if series_key in SERIES_PEOPLE:
        out = list(SERIES_PEOPLE[series_key][:2]) + out[:2]  # uyku/rahatlama/caz havası öne
    return tuple(out or PEOPLE_QUERIES["fireplace"])


def find_theme(text: str) -> Theme | None:
    """'autumn', 'sonbahar', 'deniz', 'kar', 'şömineli', 'yağmurlu', 'ormanda' gibi bir yazıdan temayı bul."""
    for v in _variants(text):
        th = _find_theme_exact(v)
        if th:
            return th
    return None


def _find_theme_exact(text: str) -> Theme | None:
    t = text.strip().lower()
    if t in ALIASES:
        return THEME_BY_KEY[ALIASES[t]]
    for th in THEMES:
        names = {th.key, th.label.lower(), EN_LABEL[th.key].lower(), th.label.lower().split()[0]}
        if t in names or t.replace("_", " ") in names:
            return th
    return None


def pick_theme(style_key: str, recent: list[str], rng: random.Random | None = None,
               allowed: tuple[str, ...] | None = None) -> Theme:
    """Stile uygun temayı tercih et; son 2 temayı tekrar etme. allowed: serinin izin verdiği temalar."""
    rng = rng or random.Random()
    pool = [t for t in THEMES if not allowed or t.key in allowed]
    preferred = [THEME_BY_KEY[k] for k in STYLE_THEMES.get(style_key, ())
                 if k not in recent[:2] and THEME_BY_KEY[k] in pool]
    others = [t for t in pool if t.key not in recent[:2] and t not in preferred]
    if preferred and (not others or rng.random() < 0.75):
        return rng.choice(preferred)
    return rng.choice(others or pool or list(THEMES))
