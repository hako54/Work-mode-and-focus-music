"""Aynı kanalda içerik serileri: Romance, Cozy Jazz, Sleep, Relaxing.

Otomatik üretim seriler arasında sırayla döner; her serinin kendi stilleri, temaları,
müzik amacı, başlık türü, açıklama maddeleri, hashtag'leri ve playlist'i vardır.
Uzun derlemeler de seri bazında yapılır (bir derlemede tek seri).
"""
from __future__ import annotations

from dataclasses import dataclass

_SOFT = ("No bright, thin, piercing or high-pitched notes, no sharp attacks, no sudden changes or loud moments. "
         "Slow fade-in intro and long soft fade-out ending.")
_ENSEMBLE = ("Arranged for a small harmonious ensemble, not a single solo instrument, all blending smoothly "
             "together.")


@dataclass(frozen=True)
class Series:
    key: str
    label: str                    # Telegram'da
    emoji: str
    genre: str                    # başlıkta: "Cozy Jazz Music"
    styles: tuple[str, ...]
    themes: tuple[str, ...]
    purpose: str                  # müzik prompt'unun amacı ("" = profilin romantik varsayılanı)
    perfect_for: tuple[str, ...]
    hashtags: str
    playlist: str
    openers: tuple[str, ...]      # şablon başlıkların başı (Claude yoksa)


SERIES: tuple[Series, ...] = (
    Series(
        "romance", "Romantik", "💕", "Romantic Love Music",
        ("romantic_solo_piano", "piano_strings_love", "moonlight_piano", "piano_cello_romance",
         "candlelight_jazz_piano", "wedding_piano", "rainy_romance_piano", "classical_romance_piano",
         "dreamy_ambient_love", "fireside_love_ballad", "romantic_sax_lounge", "acoustic_love_guitar"),
        ("fireplace", "autumn", "winter", "candlelight", "sunset", "seaside", "flowers", "rain", "night_sky", "lake",
         "forest", "picnic"),
        "",
        ("Romantic evenings & date nights", "Couples & intimate moments", "Wine & candlelit dinners",
         "Cozy nights at home", "Relaxing after a long day", "Reading & quiet time", "Late-night relaxation",
         "Anniversaries & special nights", "Falling asleep peacefully", "Massage & self-care"),
        "#RomanticMusic #LoveMusic #RomanticPiano #CozyNight #RelaxingMusic #DateNight #RomanticAmbience",
        "Romantic Love Music", (
            "Stay Close Tonight", "One More Slow Dance", "Closer by the Fire", "Our Quiet Evening",
            "Only You Tonight", "Warm Hands, Soft Lights", "Where Our Hearts Rest", "Hold Me a Little Longer",
            "A Night for Two", "Slow Love, Soft Light", "Just Breathe With Me", "Forever Starts Tonight"),
    ),
    Series(
        "jazz", "Cozy Jazz", "☕", "Cozy Jazz Music",
        ("cozy_jazz_cafe", "rainy_jazz_night", "bossa_nova_evening", "romantic_sax_lounge",
         "candlelight_jazz_piano"),
        ("cafe", "fireplace", "rain", "city_night", "candlelight", "autumn", "winter", "sunset", "picnic"),
        "Cozy smooth jazz for a relaxing evening at home or in a quiet café: soft swing feel, warm upright bass, "
        "gentle brushed drums, mellow piano, saxophone or guitar sharing the melody, relaxed and laid-back, "
        "warm and intimate sound. " + _SOFT + " " + _ENSEMBLE,
        ("Cozy evenings at home", "Working & studying", "Reading with a cup of coffee", "Rainy days",
         "Relaxing after work", "Dinner background music", "Late-night chill", "Café ambience at home",
         "Weekend mornings", "Unwinding & de-stressing"),
        "#CozyJazz #JazzMusic #RelaxingJazz #CafeMusic #SmoothJazz #RainyJazz #JazzForStudy",
        "Cozy Jazz Nights", (
            "Late Night Coffee", "Rain on the Window", "Slow Sunday Evening", "Warm Lights, Soft Jazz",
            "One More Cup", "Quiet Corner Café", "Midnight Mood", "City Lights & Coffee", "Easy Evening",
            "Soft Rain, Smooth Jazz"),
    ),
    Series(
        "sleep", "Uyku", "😴", "Sleep Music",
        ("deep_sleep_ambient", "sleep_piano_rain", "moonlight_piano", "dreamy_ambient_love"),
        ("night_sky", "rain", "winter", "lake", "fireplace"),
        "Deep sleep music: extremely slow, minimal and soothing, warm evolving ambient pads with sparse soft "
        "piano and gentle low strings, no percussion, no drums, steady very low dynamics, no melodic jumps, "
        "a continuous calm that helps the listener fall and stay asleep. " + _SOFT,
        ("Falling asleep fast", "Deep, restful sleep", "Insomnia relief", "Calming an anxious mind",
         "Bedtime routine", "Power naps", "Meditation before sleep", "Babies & toddlers sleep",
         "Night-time relaxation", "Quiet background all night"),
        "#SleepMusic #DeepSleep #RelaxingMusic #SleepingMusic #InsomniaRelief #CalmMusic #SleepPiano",
        "Sleep Music • Deep Relaxation", (
            "Drift Into Sleep", "Let the Night Hold You", "Close Your Eyes", "Soft Night, Deep Sleep",
            "Rest Now", "Under a Quiet Sky", "Sleep Peacefully", "Gentle Night", "Into the Calm",
            "Breathe and Rest"),
    ),
    Series(
        "relax", "Rahatlama", "🍃", "Relaxing Music",
        ("spa_massage_piano", "nature_relax_piano", "healing_meditation", "acoustic_love_guitar"),
        ("forest", "lake", "seaside", "flowers", "sunset", "picnic"),
        "Calm relaxing music for stress relief, spa, massage, yoga and meditation: soft piano, warm strings, "
        "gentle pads and light natural textures, slow and peaceful, spacious and healing. " + _SOFT + " "
        + _ENSEMBLE,
        ("Stress relief & anxiety", "Spa & massage", "Yoga & meditation", "Studying & focus",
         "Reading & quiet time", "Relaxing after work", "Self-care evenings", "Calm mornings",
         "Healing & mindfulness", "Peaceful background"),
        "#RelaxingMusic #StressRelief #SpaMusic #MeditationMusic #CalmMusic #HealingMusic #PeacefulMusic",
        "Relaxing Music • Calm & Healing", (
            "Let It All Go", "A Moment of Peace", "Breathe Slowly", "Calm Waters", "Quiet Mind",
            "Gentle Morning", "Soft Healing Light", "Nature's Calm", "Slow Down", "Peaceful Heart"),
    ),
)

SERIES_BY_KEY = {s.key: s for s in SERIES}
ORDER = tuple(s.key for s in SERIES)
ALIASES = {"romance": "romance", "romantik": "romance", "romantic": "romance", "ask": "romance",
           "jazz": "jazz", "caz": "jazz", "cozy": "jazz", "sleep": "sleep", "uyku": "sleep",
           "relax": "relax", "relaxing": "relax", "rahatlama": "relax", "spa": "relax", "meditasyon": "relax"}


def find_series(text: str) -> Series | None:
    t = text.strip().lower()
    for v in (t, t.rstrip("ıiuü"), t[:-2] if len(t) > 4 else t):  # 'uykuya', 'cazlı' gibi ekler
        if v in ALIASES:
            return SERIES_BY_KEY[ALIASES[v]]
    return None


def of_style(style_key: str) -> Series:
    """Bir stilin ait olduğu ilk seri (eski kayıtlar için)."""
    return next((s for s in SERIES if style_key in s.styles), SERIES[0])


def get(key: str | None) -> Series:
    return SERIES_BY_KEY.get(key or "", SERIES[0])


def next_after(key: str | None) -> Series:
    if key not in ORDER:
        return SERIES[0]
    return SERIES[(ORDER.index(key) + 1) % len(SERIES)]
