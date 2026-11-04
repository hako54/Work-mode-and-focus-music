"""Profil başına müzik stilleri ve stil seçimi.

- focus profili: birbirine yakın "odak / çalışma müziği" stilleri
- romantic profili: romantik piyano stilleri (sözsüz)

Her üretimde bir stil seçilir: son kullanılanlar atlanır, izlenmesi yüksek
stillere biraz daha fazla şans verilir (ama keşif payı her zaman kalır).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import profiles


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


FOCUS_STYLES: tuple[Style, ...] = (
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

ROMANTIC_STYLES: tuple[Style, ...] = (
    # Hepsi spa / masaj müziği yumuşaklığında: sıcak orta-pes register, uzun notalar, parlak/tiz ses yok.
    Style(
        key="romantic_solo_piano",
        label="Romantic Piano & Strings",
        thumb_word="ROMANTIC PIANO",
        base="soft romantic piano-led instrumental with a slow tender melody, accompanied by warm strings, "
             "a soft bass line and gentle pads",
        instruments=("warm felt piano with soft violas and cellos", "mellow piano with nylon guitar and warm pads",
                     "gentle piano with a soft string section and light brushed percussion"),
        moods=("tender and heartfelt", "calm and loving", "soothing and warm", "dreamy and peaceful"),
        bpm=(54, 66),
        energy=2,
        scenes=("grand piano by a tall window at sunset with rose petals on the keys",
                "couple silhouettes holding hands on a beach at golden hour, soft waves",
                "candlelit room with a piano, red roses in a vase and warm fairy lights"),
    ),
    Style(
        key="spa_massage_piano",
        label="Spa & Massage Piano",
        thumb_word="RELAX & LOVE",
        base="slow soothing spa and massage relaxation music with soft warm piano over lush ambient pads",
        instruments=("soft felt piano with warm string pad", "mellow piano with airy warm synth pads",
                     "gentle piano with soft low cello drones"),
        moods=("deeply relaxing", "soothing and healing", "peaceful and floating", "calm and comforting"),
        bpm=(50, 60),
        energy=1,
        scenes=("candlelit spa room with warm stones, rose petals and soft towels",
                "cozy fireplace room with candles, soft blankets and dim warm light",
                "calm lake at dusk with soft mist and warm sunset colors"),
    ),
    Style(
        key="dreamy_ambient_love",
        label="Dreamy Ambient Love",
        thumb_word="DREAMY LOVE",
        base="dreamy ambient romantic instrumental with slow sparse piano, long sustained warm pads and slowly "
             "evolving soft harmonies",
        instruments=("sparse warm piano with long ambient pad swells", "soft piano with warm low strings and pads",
                     "mellow electric piano with soft ambient textures"),
        moods=("weightless and calm", "warm and intimate", "slow and hypnotic", "tender and sleepy"),
        bpm=(48, 58),
        energy=1,
        scenes=("night sky full of stars over a quiet lake with a small rowing boat",
                "warm living room by a fireplace at night with two cups of tea",
                "soft sunrise over misty hills seen through a window with sheer curtains"),
    ),
    Style(
        key="piano_strings_love",
        label="Piano & Warm Strings",
        thumb_word="LOVE THEME",
        base="gentle romantic love theme with soft piano lead and warm low string orchestra, slow and smooth",
        instruments=("piano with warm low strings (violas and cellos)", "piano with soft muted string section",
                     "piano with gentle string quartet, low register"),
        moods=("emotional but calm", "bittersweet and beautiful", "hopeful and gentle", "touching and warm"),
        bpm=(54, 68),
        energy=2,
        scenes=("couple dancing slowly in a ballroom with chandeliers and golden light",
                "lovers under an umbrella on a rainy european street at night, warm lamps",
                "field of flowers at sunset with a couple silhouette in the distance"),
    ),
    Style(
        key="moonlight_piano",
        label="Moonlight Night Piano",
        thumb_word="MOONLIGHT LOVE",
        base="soft nocturne-style romantic instrumental for late night, piano with warm strings and pads, "
             "slow and quiet with warm reverb",
        instruments=("soft felt piano with muted strings and warm pad", "quiet piano with solo cello and soft pads",
                     "piano with nylon guitar and distant warm strings"),
        moods=("peaceful and intimate", "calm and loving", "sleepy and tender", "serene midnight romance"),
        bpm=(50, 62),
        energy=1,
        scenes=("moonlit balcony overlooking a calm sea with two glasses and candles",
                "night sky full of stars over a quiet lake with a small rowing boat",
                "bedroom window at night with sheer curtains, moonlight and a single rose"),
    ),
    Style(
        key="piano_cello_romance",
        label="Piano & Cello Romance",
        thumb_word="PIANO & CELLO",
        base="slow romantic duet of soft piano and warm singing cello, intimate, smooth and elegant",
        instruments=("soft piano and solo cello", "piano with cello and warm viola", "piano with cello and soft pads"),
        moods=("deep and tender", "elegant and calm", "longing and beautiful"),
        bpm=(52, 64),
        energy=2,
        scenes=("old library with a piano and a cello by the fireplace, warm amber light",
                "autumn park with golden leaves, a bench and a couple walking away",
                "vintage paris rooftop at dusk with string lights and a piano"),
    ),
    Style(
        key="candlelight_jazz_piano",
        label="Candlelight Jazz Piano",
        thumb_word="CANDLELIGHT",
        base="slow romantic jazz piano ballad instrumental with very soft brushes and warm upright bass, mellow and smooth",
        instruments=("mellow jazz piano trio with soft brushes", "warm jazz piano with soft upright bass",
                     "smooth piano ballad with gentle brushes"),
        moods=("smooth and romantic", "cozy date night", "warm and relaxed", "calm and intimate"),
        bpm=(56, 70),
        energy=3,
        scenes=("candlelit dinner table for two in a cozy restaurant with city lights outside",
                "rooftop terrace at night with candles, wine glasses and a city skyline",
                "cozy jazz lounge with a piano, red velvet and dim warm light"),
    ),
    Style(
        key="rainy_romance_piano",
        label="Rainy Romance Piano",
        thumb_word="RAINY LOVE",
        base="soft melancholic romantic piano instrumental with gentle distant rain ambience, slow and warm",
        instruments=("soft piano with light distant rain", "felt piano with soft rain and warm pad",
                     "piano with gentle rain and low strings"),
        moods=("melancholic but loving", "cozy and tender", "missing you", "quiet rainy night romance"),
        bpm=(50, 62),
        energy=1,
        scenes=("rain on a window with a love letter, candle and a cup of tea on the sill",
                "couple sharing an umbrella on a rainy night street with glowing reflections",
                "cozy cabin during rain with a piano, warm lamp and blankets"),
    ),
    Style(
        key="classical_romance_piano",
        label="Classical Romantic Piano",
        thumb_word="CLASSICAL LOVE",
        base="gentle romantic-era classical style piano with slow flowing low arpeggios and a lyrical mid-register melody",
        instruments=("warm concert grand piano played softly", "lyrical piano with soft left-hand waltz",
                     "soft piano with gentle low chamber strings"),
        moods=("poetic and tender", "graceful and calm", "timeless and elegant"),
        bpm=(54, 70),
        energy=2,
        scenes=("baroque palace hall with a grand piano, candles and roses",
                "venetian canal at sunset with a gondola and warm reflections",
                "classic garden with a fountain and blooming roses at dusk"),
    ),
    Style(
        key="wedding_piano",
        label="Wedding & First Dance Piano",
        thumb_word="FOREVER LOVE",
        base="soft romantic wedding piano instrumental, slow gentle melody with warm low strings, pure and calm",
        instruments=("warm grand piano with soft low strings", "soft piano with warm pad", "piano with gentle cello"),
        moods=("pure and devoted", "warm and gentle", "quietly joyful", "tender and calm"),
        bpm=(56, 70),
        energy=2,
        scenes=("outdoor wedding arch with white flowers at sunset in a garden",
                "bride and groom silhouettes in a field of lavender at golden hour",
                "elegant reception hall with candles, flowers and soft golden light"),
    ),
    # Küçük, uyumlu topluluklar (tek sahneli "by the Fire" tarzı videolar için ideal)
    Style(
        key="fireside_love_ballad",
        label="Fireside Love Ballad",
        thumb_word="BY THE FIRE",
        base="warm romantic love ballad instrumental for a cozy night by the fire, piano, cello and nylon acoustic "
             "guitar sharing a tender melody over soft pads and a gentle bass",
        instruments=("piano, cello and nylon guitar with soft pads", "piano and warm strings with mellow acoustic guitar",
                     "acoustic guitar lead with piano chords, soft strings and light brushes"),
        moods=("cozy and intimate", "tender and loving", "warm and comforting", "romantic and calm"),
        bpm=(56, 70),
        energy=2,
        scenes=("cozy living room by a crackling fireplace at night with an armchair and warm lamps",
                "wooden cabin interior with a fireplace, blankets and two cups of tea",
                "stone fireplace with glowing logs and soft candlelight"),
    ),
    Style(
        key="romantic_sax_lounge",
        label="Romantic Sax & Piano Lounge",
        thumb_word="LOVE NIGHT",
        base="slow romantic lounge instrumental with a mellow breathy tenor saxophone, soft piano chords, "
             "warm upright bass and very soft brushed drums",
        instruments=("mellow tenor saxophone with piano and upright bass", "soft saxophone and Rhodes piano with warm bass",
                     "breathy saxophone, piano trio and soft strings"),
        moods=("smooth and sensual", "late-night romantic", "warm wine-and-candles evening", "calm and intimate"),
        bpm=(56, 70),
        energy=3,
        scenes=("candlelit dinner for two with wine glasses and city lights outside",
                "dim jazz lounge with red velvet chairs and soft lamps",
                "rooftop terrace at night with candles and a city skyline"),
    ),
    Style(
        key="acoustic_love_guitar",
        label="Acoustic Love Guitar & Strings",
        thumb_word="TENDER LOVE",
        base="gentle romantic instrumental with fingerstyle nylon acoustic guitar, soft piano, warm strings and "
             "a light bass, slow and heartfelt",
        instruments=("nylon guitar with soft piano and strings", "two acoustic guitars with warm cello",
                     "acoustic guitar, piano and gentle pads"),
        moods=("heartfelt and sweet", "warm and hopeful", "peaceful and loving"),
        bpm=(56, 70),
        energy=2,
        scenes=("seaside terrace at sunset with lanterns", "garden bench under string lights at dusk",
                "sunlit bedroom with sheer curtains and flowers"),
    ),
    # ---- Cozy Jazz serisi
    Style(
        key="cozy_jazz_cafe",
        label="Cozy Jazz Café",
        thumb_word="COZY JAZZ",
        base="cozy smooth jazz instrumental, warm piano trio with a mellow tenor saxophone, upright bass and soft "
             "brushed drums, relaxed swing",
        instruments=("piano trio with mellow saxophone", "Rhodes piano, upright bass, brushes and soft sax",
                     "jazz guitar, piano and upright bass with brushes"),
        moods=("cozy and relaxed", "warm late-evening café", "smooth and laid-back", "calm and comforting"),
        bpm=(70, 84),
        energy=3,
        scenes=("cozy jazz café at night with warm lamps and rain on the window",),
    ),
    Style(
        key="rainy_jazz_night",
        label="Rainy Night Jazz",
        thumb_word="RAINY JAZZ",
        base="slow cozy jazz ballad instrumental for a rainy night, soft piano, warm upright bass, gentle brushes, "
             "mellow saxophone and distant soft rain",
        instruments=("soft piano and saxophone with rain", "jazz piano trio with gentle rain ambience",
                     "mellow jazz guitar and piano with rain"),
        moods=("melancholic and cozy", "quiet rainy night", "warm and intimate"),
        bpm=(62, 76),
        energy=2,
        scenes=("rainy city street at night seen from a warm café window",),
    ),
    Style(
        key="bossa_nova_evening",
        label="Bossa Nova Evening",
        thumb_word="BOSSA NOVA",
        base="soft bossa nova instrumental, gentle nylon guitar, warm piano, light shaker and soft bass, breezy "
             "and relaxed",
        instruments=("nylon guitar and piano with soft percussion", "bossa guitar with mellow flute and bass",
                     "piano, nylon guitar and soft brushes"),
        moods=("breezy and warm", "sunset terrace calm", "relaxed and sweet"),
        bpm=(72, 86),
        energy=3,
        scenes=("seaside café terrace at sunset with string lights",),
    ),
    # ---- Sleep serisi
    Style(
        key="deep_sleep_ambient",
        label="Deep Sleep Ambient",
        thumb_word="DEEP SLEEP",
        base="deep sleep ambient instrumental, very slow warm pads with sparse soft piano notes and gentle low "
             "strings, no percussion",
        instruments=("warm evolving pads with distant soft piano", "low strings and soft pads with sparse piano",
                     "soft synth pad drones with gentle piano"),
        moods=("weightless and sleepy", "calm and safe", "slow and dreamy"),
        bpm=(40, 54),
        energy=1,
        scenes=("starry night sky over a quiet lake",),
    ),
    Style(
        key="sleep_piano_rain",
        label="Sleep Piano & Rain",
        thumb_word="SLEEP & RAIN",
        base="very slow soothing sleep piano instrumental with soft rain sounds, warm pads and gentle cello, "
             "no percussion",
        instruments=("soft felt piano with rain and pads", "piano and cello with gentle rain",
                     "sparse piano with warm strings and rain"),
        moods=("drowsy and peaceful", "cozy rainy night", "quiet and comforting"),
        bpm=(44, 58),
        energy=1,
        scenes=("rain on a bedroom window at night with a dim lamp",),
    ),
    # ---- Relaxing serisi
    Style(
        key="nature_relax_piano",
        label="Nature Relaxing Piano",
        thumb_word="RELAX",
        base="calm relaxing instrumental, soft piano with warm strings, gentle pads and light nature sounds "
             "(soft stream and birds far away)",
        instruments=("soft piano with strings and stream sounds", "piano, nylon guitar and gentle forest ambience",
                     "piano with warm pads and soft water sounds"),
        moods=("peaceful and refreshing", "stress relief", "calm and grounded"),
        bpm=(54, 68),
        energy=1,
        scenes=("misty forest with a soft stream",),
    ),
    Style(
        key="healing_meditation",
        label="Healing Meditation",
        thumb_word="MEDITATION",
        base="healing meditation instrumental, warm drones, soft piano, low alto flute and gentle pads, very calm "
             "and spacious",
        instruments=("warm drones with soft piano and alto flute", "soft pads, piano and low strings",
                     "gentle piano with warm ambient textures"),
        moods=("centered and calm", "healing and gentle", "deeply relaxing"),
        bpm=(48, 60),
        energy=1,
        scenes=("calm lake at dawn with mist",),
    ),
)

ALL_STYLES: tuple[Style, ...] = FOCUS_STYLES + ROMANTIC_STYLES
STYLE_BY_KEY = {s.key: s for s in ALL_STYLES}


def active_styles() -> tuple[Style, ...]:
    """Etkin kanal profilinin stilleri."""
    return ROMANTIC_STYLES if profiles.current().key == "romantic" else FOCUS_STYLES


KEYS = ("C major", "D major", "F major", "G major", "A minor", "D minor", "E minor", "Bb major", "Eb major")


def pick_style(recent_keys: list[str], avg_views: dict[str, float], rng: random.Random | None = None,
               disabled: set[str] | None = None, only: tuple[str, ...] | None = None) -> Style:
    """Bugünün stilini seç.

    recent_keys: en yeniden eskiye son kullanılan stiller (ilk 2'si tekrar seçilmez).
    avg_views: stil -> ortalama izlenme; iyi gidenlere ağırlık verilir.
    """
    rng = rng or random.Random()
    disabled = disabled or set()
    styles = [s for s in active_styles() if not only or s.key in only] or list(active_styles())
    pool = [s for s in styles if s.key not in disabled] or list(styles)
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


def build_music_prompt(style: Style, rng: random.Random | None = None, theme=None, purpose: str = "") -> str:
    """purpose: serinin müzik amacı (boşsa profilin varsayılanı)."""
    rng = rng or random.Random()
    bpm = rng.randint(*style.bpm)
    return (
        f"Instrumental {style.base}. Featuring {rng.choice(style.instruments)}. "
        + (f"Inspired by {theme.music_hint}. " if theme else "") +
        f"Mood: {rng.choice(style.moods)}. {bpm} BPM, in {rng.choice(KEYS)}. "
        f"{purpose or profiles.current().music_purpose} "
        "No vocals, no lyrics. Clean, warm, professional mix."
    )


def build_image_prompt(style: Style, vertical: bool = False, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    framing = "vertical composition" if vertical else "wide cinematic composition"
    return (
        f"{rng.choice(style.scenes)}. {profiles.current().image_style}, "
        f"{framing}, no text, no letters, no watermark, no people facing camera"
    )
