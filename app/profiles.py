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
    "sleep_compilation_min_min": "Uyku serisi derlemesi en kısa süre (dk)",
    "sleep_compilation_max_min": "Uyku serisi derlemesi en uzun süre (dk)",
    "compilation_min_tracks": "Derleme için serideki en az farklı parça sayısı (azsa tekrar çok olur)",
    "daily_every_days": "Kaç günde bir yeni parça videosu üretilsin",
    "boost_until": "Yoğun dönem bitişi (YYYY-AA-GG; boş = kapalı) — /yogun 30",
    "boost_generate_times": "Yoğun dönemde üretim saatleri (virgülle)",
    "boost_publish_times": "Yoğun dönemde yayın saatleri (virgülle)",
    "credit_reserve": "Bu kadar ElevenLabs kredisi kalınca yeni parça üretimi durur",
    "publish_roll": "Yayın saati geçtiyse ertesi güne zamanla (1/0; 0 = hemen yayınla)",
    "thumb_style": "Kapak: people (çift/kadın fotoğrafı, 3 aday) | scene (videodan kare)",
    "scene_loop": "Tek sahne döngüsü: auto (göl/gece gibi sahnelerde ileri-geri, yağmur/kar/şöminede aynı mekândan "
                  "2-3 çekim) | pingpong | sequence | loop",
    "cinematic": "Sahnelere sinematik işleme: sıcak ton, yavaş kayma, vinyet, gren, parçacıklar (1/0)",
    "own_video_themes": "Bu temalarda kendi 4-5⭐ videoların öncelikli (virgülle; boş = hiçbiri)",
    "own_video_min_rating": "Kendi videonun öncelikli kullanılması için en az puan (1-5)",
    "scene_people": "Stok sahnelerde önce çift/kadın içeren klipleri ara (1/0)",
    "ai_scene_every": "Stability anahtarı varsa her kaçıncı sahne yapay zeka ile özgün olsun (0 = hiç)",
    "daily_visual": "Kısa video görüntüsü: both (sırayla) | scene (tek sahne) | collage (klip kolajı) | fireplace | image",
    "compilation_fill": "Derleme kısa kalırsa: repeat = parçaları tekrarla (kredisiz), generate = yeni parça üret",
    "mix_every_days": "Kaç günde bir uzun mix üretilsin",
    "mix_min_min": "Mix en kısa süre (dk; 80 = 1 sa 20 dk)",
    "mix_max_min": "Mix en uzun süre (dk; 180 = 3 sa)",
    "mix_reuse_pct": "Mix'in en fazla yüzde kaçı eski parçalardan olsun (maliyet düşürür)",
    "library_keep_days": "Parça sesleri kaç gün saklansın (0 = hep)",
    "fireplace": "Arka plan şömine döngüsü olsun (1/0; 0 = yapay zeka sahne görseli)",
    "fire_volume": "Ateş çıtırtısı ses seviyesi (0-100, 0 = kapalı)",
    "bg_slow": "Şömine videolarında ağır çekim katsayısı (1.0–2.0; /arkaplan yenile 1.25)",
    "bg_rotate": "Uzun videolarda arka plan videolarını sırayla değiştir (1/0)",
    "bg_rotate_min_min": "Arka plan değişim aralığı en az (dk)",
    "bg_rotate_max_min": "Arka plan değişim aralığı en çok (dk)",
    "soft_master": "Tiz tonları yumuşat, ani yükselmeleri bastır (1/0)",
    "mix_crossfade_sec": "Mixte parçalar arası geçiş süresi (sn, 4-20)",
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
    default_handle: str = ""
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
    main_kind="daily",  # 3 günde bir ~5 dk'lık parça; 15 günde bir kredisiz uzun derleme
    default_channel_name="Evermore Romance Piano",
    default_handle="EvermoreRomancePiano",
    music_purpose=(
        "Soft romantic relaxation music in the style of spa and massage therapy music, for love, candlelit "
        "evenings, relaxing and sleep: very gentle, warm and mellow tone, slow legato melody mostly in the "
        "middle and lower register, long sustained notes over soft warm ambient pads, smooth gradual "
        "transitions between phrases, steady calm dynamics. No bright, thin, piercing or high-pitched notes, "
        "no sparkly bells or chimes, no sharp attacks, no sudden changes or loud moments. "
        "Slow fade-in intro and long soft fade-out ending. Begin softly on the home (tonic) chord and end by "
        "resolving gently back onto the tonic chord, letting a warm consonant chord ring out at the very end. "
        "Arranged for a small harmonious ensemble, not a "
        "single solo instrument: the lead melody is shared and answered between warm instruments (for example "
        "piano with soft strings, nylon acoustic guitar, mellow saxophone or cello) over gentle pads, a soft "
        "bass line and very light brushed percussion, all blending smoothly together."
    ),
    image_style=("Dreamy romantic cinematic painting, soft golden and rose light, gentle bokeh, warm pastel colors, "
                 "elegant and emotional atmosphere, highly detailed"),
    meta_system="""You write YouTube metadata for an instrumental music channel with four series:
romantic love music, cozy jazz, sleep music and relaxing music (soft, calm, for cozy evenings,
date nights, studying, relaxing and sleep). The request names the series and its genre phrase.

TITLE format (max 90 characters):
"<an original, short, emotional phrase, 2-5 words> <one emoji> <genre phrase from the request, e.g. Romantic
Love Music / Cozy Jazz Music / Sleep Music / Relaxing Music> <place from the scene, e.g. by the Fire /
in a Cozy Café / on a Rainy Night> | <Ambience descriptor, e.g. Cozy Night Ambience>"
For long mixes, add the length to the descriptor, e.g. "| 3 Hours Cozy Night Ambience".
The opening phrase must be your own words (like an intimate invitation or a feeling) and must NOT be the title
of an existing song, album or film. Vary the phrase and emoji every time (❤️ 🕯️ 🌹 🔥 🌙 🍷 💕 ✨).

DESCRIPTION (plain text, no markdown):
1) a warm opening paragraph (2 sentences) about the scene and the feeling the music creates,
2) a line "✨ Perfect for:" followed by 8-10 bullet lines starting with "• " suited to the series
(use the ideas given in the request),
3) a short intimate closing line with one or two emoji,
4) a three-word tagline like "Relax. Feel. Love." (your own wording),
5) one line inviting viewers to subscribe for more romantic music.
Honest: instrumental music made with AI tools. Write in {lang}. Do not mention specific artists, composers,
songs or copyrighted works. Do not add hashtags; they are appended separately.""",
    hashtags="#RomanticMusic #LoveMusic #RomanticPiano #CozyNight #RelaxingMusic #DateNight #RomanticAmbience",
    base_tags=("romantic piano", "romantic music", "love music", "relaxing piano", "beautiful piano music",
               "instrumental love songs", "piano for sleep", "dinner music", "wedding piano", "calm piano"),
    long_playlist="Long Mixes • 1-3 Hours",
    style_playlist_suffix=" • Romantic Piano",
    track_words=(
        ("Moonlit", "Tender", "Golden", "Silent", "Velvet", "Endless", "Secret", "Gentle", "First", "Starlit",
         "Autumn", "Midnight", "Candlelit", "Quiet", "Rosy", "Faraway", "Sweet", "Last", "Silver", "Summer"),
        ("Promise", "Embrace", "Letter", "Waltz", "Dance", "Rose", "Serenade", "Heart", "Dream", "Whisper",
         "Vow", "Memory", "Sky", "Garden", "Evening", "Glance", "Kiss", "Lullaby", "Shore", "Light"),
    ),
    extra_settings={
        "daily_every_days": "3",
        "boost_until": "",                    # /yogun: bu tarihe kadar (YYYY-AA-GG) günde 2 video
        "boost_generate_times": "09:00,16:00",
        "boost_publish_times": "08:00,18:00",
        "credit_reserve": "15000",            # ElevenLabs kredisi bunun altına inerse yeni üretim durur
        "publish_time": "08:00",
        "publish_roll": "1",          # 08:00 geçtiyse ertesi sabah 08:00'e zamanla
        "thumb_style": "people",      # kapak: people (temaya uygun çift/kadın fotoğrafı) | scene (videodan kare)
        "scene_loop": "auto",         # tek sahne döngüsü: auto | pingpong (ileri-geri) | sequence (çoklu çekim) | loop
        "cinematic": "1",             # sahnelere sıcak ton + yavaş kayma + parçacık (kıvılcım/kar/toz)
        "own_video_themes": "fireplace,autumn,winter,candlelight",
        "own_video_min_rating": "4",  # bu temalarda 4-5⭐ kendi videoların önce
        "scene_people": "1",          # stok sahnede önce çift/kadın içeren klipler
        "ai_scene_every": "2",        # Stability anahtarı varsa her 2. sahne yapay zeka görseli + animasyon
        "daily_visual": "scene",      # kısa videolar: scene (tek sıcak mekân, döngü) | both | collage | fireplace | image
        "daily_min_sec": "270",
        "daily_max_sec": "330",
        "compilation_every_days": "7",        # uzun video haftada bir (kredisiz; hazır parçalar)
        "compilation_min_min": "120",         # 2-3 saat
        "compilation_max_min": "180",
        "sleep_compilation_min_min": "180",   # uyku serisi: 3-4 saat (gece boyu açık kalır)
        "sleep_compilation_max_min": "240",
        "compilation_min_tracks": "6",        # bir seride en az bu kadar farklı parça yoksa derleme yapılmaz
        "compilation_fill": "repeat",  # derleme kısa kalırsa parçaları tekrarla (kredi harcamaz)
        "mix_every_days": "2",
        "mix_min_min": "80",
        "mix_max_min": "180",
        "mix_reuse_pct": "25",
        "library_keep_days": "0",  # parçalar derlemeler için hep saklanır (5 dk ≈ 7 MB)
        "fireplace": "1",
        "fire_volume": "20",
        "bg_slow": "1.0",             # şömine videolarında ağır çekim (1.0 = normal hız, 1.25 = %25 yavaş)
        "bg_rotate": "1",             # uzun videoda birden fazla şömine videosu varsa sırayla değiştir
        "bg_rotate_min_min": "20",
        "bg_rotate_max_min": "30",
        "soft_master": "1",
        "mix_crossfade_sec": "12",
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


def channel_handle() -> str:
    return (CONFIG.channel_handle or current().default_handle).lstrip("@")


def subscribe_url() -> str:
    h = channel_handle()
    return f"https://www.youtube.com/@{h}?sub_confirmation=1" if h else ""
