"""Kanal profilleri: aynı kod tabanı farklı kanallar için çalışır.

`CHANNEL_PROFILE` ortam değişkeni hangi profilin kullanılacağını seçer:
- focus    : günlük 3-5 dk odak müziği + 15 günde bir derleme (varsayılan)
- romantic : 1 saat 20 dk – 3 saat+ uzunluğunda romantik piyano mixleri

Her profil kendi Railway servisinde, kendi volume'u (veritabanı) ve kendi
YouTube kanalıyla çalışır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import CONFIG

BASE_SETTINGS: dict[str, str] = {
    "generate_time": "09:00",        # üretim + onaya gönderme (yerel saat)
    "publish_time": "17:00",         # yayın saati (yerel saat; İstanbul 17:00 = ABD doğu 10:00)
    "daily_min_sec": "180",
    "daily_max_sec": "300",
    "make_shorts": "1",
    "short_seconds": "45",
    "short_delay_hours": "5",        # Short, ana videodan kaç saat sonra yayınlansın
    "reminder_hours": "4",           # onay bekleyen için hatırlatma aralığı
    "auto_approve_hours": "0",       # 0 = kapalı; >0 ise bu kadar saat cevap yoksa otomatik onay
    "paused": "0",
}

SETTING_HELP: dict[str, str] = {
    "generate_time": "Üretim saati (SS:DD)",
    "publish_time": "Yayın saati (SS:DD)",
    "daily_min_sec": "Parça en kısa süre (sn)",
    "daily_max_sec": "Parça en uzun süre (sn)",
    "compilation_every_days": "Derleme sıklığı (gün)",
    "compilation_min_min": "Derleme en kısa süre (dk)",
    "compilation_max_min": "Derleme en uzun süre (dk)",
    "mix_every_days": "Kaç günde bir uzun mix üretilsin",
    "mix_min_min": "Mix en kısa süre (dk; 80 = 1 sa 20 dk)",
    "mix_max_min": "Mix en uzun süre (dk; 180 = 3 sa)",
    "mix_reuse_pct": "Mix'in en fazla yüzde kaçı eski parçalardan olsun (maliyet düşürür)",
    "library_keep_days": "Parça sesleri kaç gün saklansın (0 = hep)",
    "make_shorts": "Short üret (1/0)",
    "short_seconds": "Short uzunluğu (sn, en fazla 59)",
    "short_delay_hours": "Short yayın gecikmesi (saat)",
    "reminder_hours": "Onay hatırlatma aralığı (saat)",
    "auto_approve_hours": "Cevapsız kalırsa otomatik onay (saat, 0=kapalı)",
    "paused": "Otomasyon duraklatıldı mı (1/0)",
}


@dataclass(frozen=True)
class Profile:
    key: str
    main_kind: str                    # "daily" (tek parça) | "mix" (uzun, çok parçalı)
    default_channel_name: str
    music_purpose: str                # müzik prompt'unun sonuna eklenen kullanım amacı
    image_style: str                  # görsel prompt'unun sanat yönü
    meta_system: str                  # Claude sistem talimatı ({lang} içerir)
    hashtags: str
    base_tags: tuple[str, ...]
    long_playlist: str
    style_playlist_suffix: str
    track_words: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
    extra_settings: dict[str, str] = field(default_factory=dict)


FOCUS = Profile(
    key="focus",
    main_kind="daily",
    default_channel_name="Work Mode & Focus Music",
    music_purpose=(
        "Designed as background music for deep work, studying and focus: steady energy, "
        "no sudden drops or loud changes, smooth loop-friendly arrangement, gentle intro and soft ending."
    ),
    image_style=("Cozy lo-fi anime illustration style, soft lighting, rich warm colors, calm atmosphere, "
                 "highly detailed"),
    meta_system="""You write YouTube metadata for an instrumental focus / work / study music channel.
Every video must feel distinct: vary the title structure, wording and emoji, never reuse a recent title pattern.
Titles are honest about the content (instrumental AI-assisted focus music), search-friendly and not clickbait.
Descriptions: an evocative opening line about the scene and mood, a line on what it is good for
(deep work, coding, studying, reading), and a short invitation to subscribe. Write in {lang}.
Do not mention specific artists or copyrighted works. Do not add hashtags; they are appended separately.""",
    hashtags="#focusmusic #studymusic #workmusic",
    base_tags=("focus music", "study music", "work music", "deep work", "concentration music", "lofi",
               "music for coding", "productivity music", "background music"),
    long_playlist="Long Focus Mixes (30-60 min)",
    style_playlist_suffix=" • Focus Music",
    extra_settings={
        "compilation_every_days": "15",
        "compilation_min_min": "30",
        "compilation_max_min": "60",
    },
)

ROMANTIC = Profile(
    key="romantic",
    main_kind="mix",
    default_channel_name="Romantic Piano Moments",
    music_purpose=(
        "Romantic instrumental piano music for love, candlelit evenings, relaxation and sleep: tender, "
        "heartfelt and memorable melody, expressive but gentle dynamics, no harsh or loud moments, "
        "slow emotional build, warm intimate sound, gentle intro and soft natural ending."
    ),
    image_style=("Dreamy romantic cinematic painting, soft golden and rose light, gentle bokeh, warm pastel colors, "
                 "elegant and emotional atmosphere, highly detailed"),
    meta_system="""You write YouTube metadata for an instrumental romantic piano music channel
(long mixes of tender love-themed piano music for relaxing, date nights, dinner, reading and sleep).
Every video must feel distinct: vary the title structure, wording and emoji, never reuse a recent title pattern.
Titles are honest (instrumental, AI-assisted romantic piano music), search-friendly, mention the length
(e.g. "3 Hours", "1 Hour 30 Minutes") and are not clickbait. Use at most one or two tasteful emoji (💕 🌹 🕯️ 🎹 ✨).
Descriptions: an evocative, warm opening about the scene and feeling, a line on what it is good for
(romantic evenings, relaxing, studying, sleeping, wedding or dinner background), and a short invitation
to subscribe. Write in {lang}. Do not mention specific artists, composers, songs or copyrighted works.
Do not add hashtags; they are appended separately.""",
    hashtags="#romanticmusic #pianomusic #lovemusic",
    base_tags=("romantic piano", "romantic music", "love music", "relaxing piano", "beautiful piano music",
               "instrumental love songs", "piano for sleep", "dinner music", "wedding piano", "calm piano"),
    long_playlist="Romantic Piano • Long Mixes",
    style_playlist_suffix=" • Romantic Piano",
    track_words=(
        ("Moonlit", "Tender", "Golden", "Silent", "Velvet", "Endless", "Secret", "Gentle", "First", "Starlit",
         "Autumn", "Midnight", "Candlelit", "Quiet", "Rosy", "Faraway", "Sweet", "Last", "Silver", "Summer"),
        ("Promise", "Embrace", "Letter", "Waltz", "Dance", "Rose", "Serenade", "Heart", "Dream", "Whisper",
         "Vow", "Memory", "Sky", "Garden", "Evening", "Glance", "Kiss", "Lullaby", "Shore", "Light"),
    ),
    extra_settings={
        "mix_every_days": "2",
        "mix_min_min": "80",
        "mix_max_min": "180",
        "mix_reuse_pct": "25",
        "library_keep_days": "120",
    },
)

PROFILES: dict[str, Profile] = {p.key: p for p in (FOCUS, ROMANTIC)}
_override: str | None = None


def current() -> Profile:
    key = _override or CONFIG.channel_profile
    if key not in PROFILES:
        raise ValueError(f"Bilinmeyen CHANNEL_PROFILE: {key!r} (seçenekler: {', '.join(PROFILES)})")
    return PROFILES[key]


def set_active(key: str | None) -> None:
    """Testler ve araçlar için profili çalışma anında değiştir (None = ortam değişkeni)."""
    global _override
    _override = key


def default_settings() -> dict[str, str]:
    return {**BASE_SETTINGS, **current().extra_settings}


def channel_name() -> str:
    return CONFIG.channel_name or current().default_channel_name
