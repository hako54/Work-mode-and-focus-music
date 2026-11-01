"""Başlık, açıklama ve etiket üretimi (Claude API).

ANTHROPIC_API_KEY yoksa veya istek başarısız olursa şablon tabanlı yedek kullanılır.
"""
from __future__ import annotations

import logging
import random

import anthropic
from pydantic import BaseModel, Field

from . import profiles
from .config import CONFIG
from .media import fmt_long
from .styles import Style

log = logging.getLogger(__name__)


class VideoMeta(BaseModel):
    title: str = Field(description="YouTube title, max 90 characters")
    description: str = Field(description="YouTube description body, 3 short paragraphs, no timestamps")
    tags: list[str] = Field(description="10-18 search tags, lowercase")
    thumbnail_text: str = Field(description="2-3 word thumbnail headline, uppercase")
    track_name: str = Field(description="Short poetic name for the music track, 2-4 words")


def _client() -> anthropic.Anthropic | None:
    return anthropic.Anthropic(api_key=CONFIG.anthropic_api_key) if CONFIG.anthropic_api_key else None


def generate(kind: str, style: Style, duration_sec: float, scene: str, recent_titles: list[str],
             extra: str = "") -> VideoMeta:
    client = _client()
    if client:
        minutes = round(duration_sec / 60)
        what = {"daily": "single track", "compilation": "long mix of the channel's best tracks",
                "mix": "long continuous mix of new tracks"}.get(kind, kind)
        prompt = (
            f"Video type: {kind} ({what}, ~{minutes} min = {fmt_long(duration_sec)})\n"
            f"Music style: {style.label} — {style.base}\n"
            f"Visual scene: {scene}\n"
            f"Channel: {profiles.channel_name()}\n"
            f"Recent titles to avoid repeating:\n" + "\n".join(f"- {t}" for t in recent_titles[:15]) +
            (f"\n\nExtra context: {extra}" if extra else "")
        )
        try:
            resp = client.messages.parse(
                model=CONFIG.claude_model,
                max_tokens=4000,
                system=profiles.current().meta_system.format(lang="English" if CONFIG.content_language == "en" else CONFIG.content_language),
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
                output_format=VideoMeta,
            )
            if resp.stop_reason != "refusal" and resp.parsed_output:
                return _clean(resp.parsed_output)
            log.warning("Claude meta üretmedi (stop_reason=%s), şablona geçiliyor", resp.stop_reason)
        except anthropic.APIError as e:
            log.warning("Claude API hatası: %s — şablona geçiliyor", e)
    return fallback(kind, style, duration_sec)


def fallback(kind: str, style: Style, duration_sec: float, rng: random.Random | None = None) -> VideoMeta:
    rng = rng or random.Random()
    if profiles.current().key == "romantic":
        return _fallback_romantic(kind, style, duration_sec, rng)
    minutes = round(duration_sec / 60)
    if kind in ("compilation", "mix"):
        title = rng.choice([
            f"{minutes} Min {style.label} Mix for Deep Work & Study",
            f"Focus Mode: {minutes} Minutes of {style.label} for Productivity",
            f"{style.label} Focus Session — {minutes} Min Mix to Work & Study",
        ])
    else:
        title = rng.choice([
            f"{style.label} for Focus & Work ☕",
            f"Get Into Flow — {style.label} Beats to Study",
            f"{style.label} • Calm Music for Deep Concentration",
        ])
    desc = (
        f"{style.label} to help you focus, work and study.\n\n"
        "Perfect for deep work sessions, coding, reading and calm productivity.\n\n"
        "Subscribe for a new focus track every day and a long mix every two weeks."
    )
    tags = [*profiles.current().base_tags, style.label.lower()]
    return VideoMeta(title=title, description=desc, tags=tags, thumbnail_text=style.thumb_word,
                     track_name=rng.choice(["Quiet Hours", "Soft Focus", "Late Light", "Paper Moon", "Still Water"]))


def _fallback_romantic(kind: str, style: Style, duration_sec: float, rng: random.Random) -> VideoMeta:
    length = fmt_long(duration_sec)
    title = rng.choice([
        f"{length} of {style.label} 💕 Beautiful Romantic Music for Love & Relaxation",
        f"Romantic Piano Music 🌹 {length} {style.label} for Date Night & Dinner",
        f"{length} Relaxing Romantic Piano 🕯️ {style.label} for Sleep & Calm",
        f"Love Songs on Piano 🎹 {length} of Tender {style.label}",
    ])
    desc = (
        f"{length} of tender, heartfelt {style.label.lower()} — soft melodies to share with someone you love.\n\n"
        "Perfect for romantic evenings, candlelit dinners, relaxing after a long day, reading or drifting off to sleep.\n\n"
        "Subscribe for new long romantic piano mixes every few days. 💕"
    )
    tags = [*profiles.current().base_tags, style.label.lower(), f"{length.lower()} romantic piano"]
    return VideoMeta(title=title, description=desc, tags=tags, thumbnail_text=style.thumb_word,
                     track_name=random_track_name(rng))


def random_track_name(rng: random.Random, taken: set[str] | None = None) -> str:
    """Profilin kelime havuzundan 'Moonlit Promise' gibi bir parça adı üret."""
    first, second = profiles.current().track_words
    if not first:
        first, second = ("Quiet", "Soft", "Late", "Paper", "Still"), ("Hours", "Focus", "Light", "Moon", "Water")
    taken = taken or set()
    for _ in range(50):
        name = f"{rng.choice(first)} {rng.choice(second)}"
        if name not in taken:
            return name
    return f"{rng.choice(first)} {rng.choice(second)} {len(taken) + 1}"


def _clean(meta: VideoMeta) -> VideoMeta:
    title = meta.title.replace("<", "").replace(">", "").strip()[:100]
    tags, total = [], 0
    for t in meta.tags:  # YouTube etiket toplamı 500 karakter sınırı
        t = t.replace("<", "").replace(">", "").replace(",", " ").strip()
        if t and total + len(t) + 1 < 450:
            tags.append(t)
            total += len(t) + 1
    return meta.model_copy(update={"title": title, "tags": tags,
                                   "description": meta.description.replace("<", "").replace(">", "")})


def full_description(body: str, tracklist: str = "", extra_links: str = "") -> str:
    parts = [body.strip()]
    if tracklist:
        parts.append("Tracklist:\n" + tracklist)
    if extra_links:
        parts.append(extra_links)
    parts.append("Music and visuals are created with AI tools and curated by the channel.")
    parts.append(profiles.current().hashtags)
    return "\n\n".join(parts)[:4900]
