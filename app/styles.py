"""Birbirine yakın "odak / çalışma müziği" stilleri ve günlük stil seçimi.

Her gün bir stil seçilir: son günlerde kullanılanlar atlanır, izlenmesi yüksek
stillere biraz daha fazla şans verilir (ama keşif payı her zaman kalır).
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    key: str
    label: str                 # Telegram'da görünen ad
    thumb_word: str            # küçük resimdeki kısa etiket
    base: str                  # müzik prompt'unun çekirdeği
    instruments: tuple[str, ...]
    moods: tuple[str, ...]
    bpm: tuple[int, int]
    energy: int                # 1 (çok sakin) – 5 (hareketli); derleme sıralaması için
    scenes: tuple[str, ...]    # görsel sahneleri


STYLES: tuple[Style, ...] = (
    Style(
        key="lofi_hiphop",
        label="Lo-fi Hip Hop",
        thumb_word="LO-FI FOCUS",
        base="lo-fi hip hop instrumental with dusty boom-bap drums, soft vinyl crackle and tape saturation",
        instruments=("mellow Rhodes electric piano", "warm muted guitar chops", "soft jazzy piano chords",
                     "dreamy synth pad and sub bass"),
        moods=("calm and focused", "cozy and warm", "late-night productive", "relaxed but steady"),
        bpm=(72, 86),
        energy=3,
        scenes=("cozy desk by a window at night with a warm lamp, laptop and coffee, city lights outside",
                "small attic study room with plants, books and soft evening light",
                "rainy window with a desk, notebook and a steaming mug, neon city reflections"),
    ),
    Style(
        key="chillhop_jazz",
        label="Jazzy Chillhop",
        thumb_word="JAZZ & WORK",
        base="jazzy chillhop instrumental with brushed drums, upright bass and swung groove",
        instruments=("smooth jazz guitar", "vibraphone melodies", "muted trumpet phrases",
                     "warm grand piano voicings"),
        moods=("uplifting and smooth", "sophisticated and calm", "sunny afternoon focus"),
        bpm=(80, 92),
        energy=4,
        scenes=("sunlit café corner with a laptop, croissant and latte, morning light",
                "modern home office with a record player, plants and golden hour light",
                "jazz bar after hours, empty stage, warm amber lights, notebook on the table"),
    ),
    Style(
        key="ambient_piano",
        label="Ambient Piano",
        thumb_word="CALM PIANO",
        base="soft felt piano instrumental with gentle ambient pads, spacious reverb, no drums",
        instruments=("intimate felt piano", "delicate piano with string pad", "piano with soft cello swells"),
        moods=("peaceful and introspective", "gentle and clear-minded", "serene morning calm"),
        bpm=(60, 72),
        energy=1,
        scenes=("minimalist room with a piano, sheer curtains and soft morning light",
                "quiet library with tall windows and dust in sunbeams",
                "misty lake at dawn seen from a wooden cabin desk"),
    ),
    Style(
        key="deep_focus_ambient",
        label="Deep Focus Ambient",
        thumb_word="DEEP FOCUS",
        base="deep focus ambient instrumental with slowly evolving warm textures, minimal and non-distracting",
        instruments=("analog synth drones and soft arpeggios", "granular pads and distant bells",
                     "warm sub tones with airy textures"),
        moods=("immersive and steady", "flow state", "spacious and clear"),
        bpm=(60, 70),
        energy=1,
        scenes=("futuristic quiet workspace overlooking a starry sky",
                "minimal desk in a dark room with a glowing monitor and soft blue light",
                "observatory at night with a telescope and a calm galaxy view"),
    ),
    Style(
        key="chillwave_synth",
        label="Chillwave / Soft Synth",
        thumb_word="SYNTH FOCUS",
        base="chillwave instrumental with warm analog synths, soft drum machine and nostalgic retro feel",
        instruments=("lush Juno-style pads", "gentle synth lead and chorus guitar", "plucky arpeggiator and soft bass"),
        moods=("nostalgic and dreamy", "smooth night drive focus", "calm retro glow"),
        bpm=(85, 98),
        energy=4,
        scenes=("retro 80s workstation with a CRT monitor, neon purple sunset outside",
                "night city skyline from a high apartment desk, pink and teal neon",
                "coastal highway at dusk seen from a window workspace, synthwave colors"),
    ),
    Style(
        key="rain_lofi",
        label="Rainy Lo-fi",
        thumb_word="RAINY FOCUS",
        base="mellow lo-fi instrumental blended with gentle rain ambience, soft drums and warm tape tone",
        instruments=("soft Rhodes and rain", "nylon guitar with rain", "muted piano with light rain and thunder far away"),
        moods=("cozy and safe", "melancholic but calm", "quiet rainy evening focus"),
        bpm=(68, 80),
        energy=2,
        scenes=("rain on a big window, desk with a warm lamp and books, blurred city lights",
                "cabin in the forest during rain, wooden desk, candle light",
                "tokyo street in the rain seen from a small café window"),
    ),
    Style(
        key="downtempo_organic",
        label="Organic Downtempo",
        thumb_word="FLOW STATE",
        base="organic downtempo instrumental with soft electronic beats, earthy percussion and warm bass",
        instruments=("kalimba and hand percussion", "soft marimba and deep bass", "flute textures and gentle synths"),
        moods=("grounded and focused", "flowing and positive", "calm productive energy"),
        bpm=(88, 100),
        energy=3,
        scenes=("bright workspace full of plants with sunlight and a laptop",
                "wooden desk on a balcony overlooking green hills",
                "zen garden study room with soft daylight"),
    ),
    Style(
        key="acoustic_lofi",
        label="Acoustic Lo-fi",
        thumb_word="STUDY GUITAR",
        base="acoustic lo-fi instrumental with fingerstyle guitar, soft brushed beat and warm room tone",
        instruments=("fingerstyle acoustic guitar", "nylon guitar and soft piano", "guitar and gentle glockenspiel"),
        moods=("warm and focused", "light and hopeful", "relaxed concentration"),
        bpm=(70, 84),
        energy=2,
        scenes=("autumn window with a desk, guitar leaning on the wall, warm tea",
                "sunny countryside room with a notebook and wildflowers",
                "cozy bedroom desk with fairy lights and an open book"),
    ),
)

STYLE_BY_KEY = {s.key: s for s in STYLES}
KEYS = ("C major", "D major", "F major", "G major", "A minor", "D minor", "E minor", "Bb major", "Eb major")


def pick_style(recent_keys: list[str], avg_views: dict[str, float], rng: random.Random | None = None,
               disabled: set[str] | None = None) -> Style:
    """Bugünün stilini seç.

    recent_keys: en yeniden eskiye son kullanılan stiller (ilk 2'si tekrar seçilmez).
    avg_views: stil -> ortalama izlenme; iyi gidenlere ağırlık verilir.
    """
    rng = rng or random.Random()
    disabled = disabled or set()
    pool = [s for s in STYLES if s.key not in disabled] or list(STYLES)
    blocked = set(recent_keys[:2])
    candidates = [s for s in pool if s.key not in blocked] or pool

    best = max(avg_views.values(), default=0.0)
    weights = []
    for s in candidates:
        perf = avg_views.get(s.key)
        # Hiç denenmemiş stile yüksek keşif ağırlığı; diğerleri 1..3 arası.
        w = 2.5 if perf is None else 1.0 + (2.0 * perf / best if best > 0 else 0.0)
        weights.append(w)
    return rng.choices(candidates, weights=weights, k=1)[0]


def build_music_prompt(style: Style, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    bpm = rng.randint(*style.bpm)
    return (
        f"Instrumental {style.base}. Featuring {rng.choice(style.instruments)}. "
        f"Mood: {rng.choice(style.moods)}. {bpm} BPM, in {rng.choice(KEYS)}. "
        "Designed as background music for deep work, studying and focus: steady energy, "
        "no sudden drops or loud changes, smooth loop-friendly arrangement, gentle intro and soft ending. "
        "No vocals, no lyrics. Clean, warm, professional mix."
    )


def build_image_prompt(style: Style, vertical: bool = False, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    framing = "vertical composition" if vertical else "wide cinematic composition"
    return (
        f"{rng.choice(style.scenes)}. Cozy lo-fi anime illustration style, soft lighting, rich warm colors, "
        f"calm atmosphere, highly detailed, {framing}, no text, no letters, no watermark, no people facing camera"
    )
