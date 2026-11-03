"""Üretim hattı: günlük video + Short, 15 günlük derleme, uzun mix (romantic), onay sonrası yükleme."""
from __future__ import annotations

import logging
import math
import random
import shutil
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import fireplace, media, metadata, profiles, stock, visuals
from .config import CONFIG
from .db import Database, iso, parse_iso, tags_of, utcnow
from .music import get_provider
from .styles import STYLE_BY_KEY, Style, active_styles, build_image_prompt, build_music_prompt, pick_style
from .themes import EN_LABEL, THEME_BY_KEY, Theme, pick_theme

log = logging.getLogger(__name__)
MIX_XFADE = 6.0          # uzun mixte parçalar arası crossfade (sn)
LONG_KINDS = ("compilation", "mix")  # çok parçalı, compilation_tracks kullanan türler
Progress = Callable[[str], None]


def _noop(_: str) -> None:
    pass


class Pipeline:
    def __init__(self, db: Database):
        self.db = db
        self.tz = ZoneInfo(CONFIG.timezone)

    # ------------------------------------------------------------------ helpers
    def _dir(self, name: str) -> Path:
        d = CONFIG.media_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def recent_titles(self, n: int = 20) -> list[str]:
        return [r["title"] for r in self.db.query(
            "SELECT title FROM videos WHERE title IS NOT NULL AND kind != 'short' ORDER BY id DESC LIMIT ?", (n,))]

    def style_performance(self) -> dict[str, float]:
        rows = self.db.query(
            "SELECT style_key, AVG(views) v FROM videos WHERE kind IN ('daily', 'mix') AND status = 'published' "
            "GROUP BY style_key")
        return {r["style_key"]: float(r["v"] or 0) for r in rows}

    def disabled_styles(self) -> set[str]:
        raw = self.db.get_setting("disabled_styles")
        return {s for s in raw.split(",") if s}

    def next_publish_at(self, now: datetime | None = None) -> datetime | None:
        """Bugünün yayın saati henüz geçmediyse o zaman; geçtiyse None (= hemen yayınla)."""
        now = now or utcnow()
        hh, mm = (int(x) for x in self.db.get_setting("publish_time").split(":"))
        local = now.astimezone(self.tz)
        target = datetime.combine(local.date(), time(hh, mm), tzinfo=self.tz)
        # YouTube zamanlanmış yayın için en az birkaç dakika ileri bir zaman ister.
        if target - now > timedelta(minutes=15):
            return target
        if self.db.get_setting("publish_roll") == "1":  # ör. 08:00 geçti -> yarın 08:00
            return datetime.combine(local.date() + timedelta(days=1), time(hh, mm), tzinfo=self.tz)
        return None

    # ------------------------------------------------------------------ daily
    def create_daily(self, style_key: str | None = None, progress: Progress = _noop) -> int:
        rng = random.Random()
        recent = [r["style_key"] for r in self.db.query(
            "SELECT style_key FROM videos WHERE kind = 'daily' ORDER BY id DESC LIMIT 5")]
        style = STYLE_BY_KEY[style_key] if style_key else pick_style(
            recent, self.style_performance(), rng, self.disabled_styles())
        lo, hi = self.db.get_int("daily_min_sec"), self.db.get_int("daily_max_sec")
        duration = rng.randint(lo, hi)

        theme = self._pick_theme(style, rng) if profiles.current().key == "romantic" else None
        track_id = self.db.add_track(style_key=style.key, prompt=build_music_prompt(style, rng, theme),
                                     theme=theme.key if theme else None)
        video_id = self.db.add_video(kind="daily", track_id=track_id, style_key=style.key, status="building")
        try:
            progress(f"🎵 Müzik üretiliyor: {style.label}" + (f" · {theme.emoji} {theme.label}" if theme else "")
                     + f" (~{duration // 60} dk {duration % 60} sn)")
            self._make_track_audio(track_id, duration)
            scene = self._daily_visuals(video_id, style, rng, progress)
            progress("✍️ Başlık ve açıklama yazılıyor")
            self._write_meta(video_id, style, scene)
            progress("🎬 Video render ediliyor")
            self._render_daily(video_id)
            if self.db.get_setting("make_shorts") == "1":
                progress("📱 Short hazırlanıyor")
                self._make_short(video_id)
            self.db.update_video(video_id, status="pending")
        except Exception as e:
            self.db.update_video(video_id, status="failed", error=str(e)[:1000])
            raise
        return video_id

    def unused_tracks(self) -> list:
        """Sesi duran ama hiçbir videoda yayınlanmamış / onay beklemeyen parçalar (ör. yarıda kalan mixten)."""
        taken = {r["track_id"] for r in self.db.query(
            "SELECT track_id FROM videos WHERE track_id IS NOT NULL AND status NOT IN ('rejected', 'failed') "
            "UNION SELECT ct.track_id FROM compilation_tracks ct JOIN videos v ON v.id = ct.video_id "
            "WHERE v.status NOT IN ('rejected', 'failed')")}
        return [t for t in self.db.query("SELECT * FROM tracks WHERE audio_path IS NOT NULL "
                                         "AND duration_sec IS NOT NULL ORDER BY id")
                if t["id"] not in taken and Path(t["audio_path"]).exists()]

    def create_daily_from_track(self, track_id: int, progress: Progress = _noop) -> int:
        """Kütüphanedeki hazır bir parçadan video yap (yeni müzik üretmez, kredi harcamaz)."""
        rng = random.Random()
        t = self.db.track(track_id)
        style = STYLE_BY_KEY.get(t["style_key"], active_styles()[0])
        if not t["theme"] and profiles.current().key == "romantic":
            self.db.update_track(track_id, theme=self._pick_theme(style, rng).key)
        video_id = self.db.add_video(kind="daily", track_id=track_id, style_key=style.key, status="building")
        try:
            scene = self._daily_visuals(video_id, style, rng, progress)
            progress("✍️ Başlık ve açıklama yazılıyor")
            self._write_meta(video_id, style, scene)
            progress("🎬 Video render ediliyor")
            self._render_daily(video_id)
            if self.db.get_setting("make_shorts") == "1":
                progress("📱 Short hazırlanıyor")
                self._make_short(video_id)
            self.db.update_video(video_id, status="pending")
        except Exception as e:
            self.db.update_video(video_id, status="failed", error=str(e)[:1000])
            raise
        return video_id

    def discard_track(self, track_id: int) -> None:
        shutil.rmtree(CONFIG.media_dir / f"track_{track_id}", ignore_errors=True)
        self.db.update_track(track_id, audio_path=None, image_path=None)

    def _make_track_audio(self, track_id: int, duration: int) -> None:
        t = self.db.track(track_id)
        d = self._dir(f"track_{track_id}")
        raw = get_provider().compose(t["prompt"], duration, d / "raw.mp3")
        if self.db.get_setting("soft_master") == "1":  # romantic: uzun yumuşak giriş/çıkış, tizler kısık
            final = media.master_audio(raw, d / "track.mp3", fade_in=5.0, fade_out=10.0, soft=True)
        else:
            final = media.master_audio(raw, d / "track.mp3")
        raw.unlink(missing_ok=True)
        self.db.update_track(track_id, audio_path=str(final), duration_sec=media.duration(final))

    def _make_track_image(self, track_id: int, style: Style, rng: random.Random) -> str:
        prompt = build_image_prompt(style, rng=rng)
        d = self._dir(f"track_{track_id}")
        img = visuals.generate_image(prompt, d / "image.png", "16:9", seed=rng.randint(1, 2**31))
        self.db.update_track(track_id, image_path=str(img))
        return prompt.split(".")[0]

    FIRE_SCENE = "a cozy wood fireplace burning at night, warm flickering flames and glowing embers"

    def _pick_theme(self, style: Style, rng: random.Random) -> Theme:
        recent = [r["theme"] for r in self.db.query(
            "SELECT theme FROM tracks WHERE theme IS NOT NULL ORDER BY id DESC LIMIT 5")]
        return pick_theme(style.key, recent, rng)

    def _theme_of(self, video_id: int) -> Theme | None:
        v = self.db.video(video_id)
        if not v["track_id"]:
            return None
        return THEME_BY_KEY.get(self.db.track(v["track_id"])["theme"] or "")

    def _collage(self, video_id: int, kind: str = "h") -> Path | None:
        p = CONFIG.media_dir / f"video_{video_id}" / ("collage.mp4" if kind == "h" else "collage_v.mp4")
        return p if p.exists() else None

    def _daily_visuals(self, video_id: int, style: Style, rng: random.Random, progress: Progress = _noop) -> str:
        """Kısa video görüntüsü: temaya uygun klip kolajı → şömine → yapay zeka/prosedürel görsel."""
        mode = self.db.get_setting("daily_visual") or ("fireplace" if self.fireplace_on() else "image")
        d = self._dir(f"video_{video_id}")
        for f in ("collage.mp4", "collage_v.mp4", "background.txt"):
            (d / f).unlink(missing_ok=True)
        theme = self._theme_of(video_id)
        if mode == "collage" and theme and stock.available():
            progress(f"🎞 {theme.emoji} {theme.label} temalı klipler hazırlanıyor")
            try:
                if self._build_collage(video_id, theme, rng):
                    return theme.scene
            except Exception as e:  # noqa: BLE001
                log.warning("Kolaj hazırlanamadı, yedeğe geçiliyor: %s", e)
        if mode in ("collage", "fireplace") and self.fireplace_on():
            progress("🔥 Şömine arka planı seçiliyor")
            self._daily_fireplace(video_id, rng)
            return theme.scene if theme else self.FIRE_SCENE
        progress("🖼 Görsel hazırlanıyor")
        scene = self._make_track_image(self.db.video(video_id)["track_id"], style, rng)
        return theme.scene if theme else scene

    def _build_collage(self, video_id: int, theme: Theme, rng: random.Random) -> bool:
        d = self._dir(f"video_{video_id}")
        used = {r["provider_id"] for r in self.db.query("SELECT provider_id FROM stock_used")}
        items = stock.fetch(theme, d / "stock", used, rng)
        try:
            if len(items) < 3:
                log.warning("Kolaj için yeterli içerik yok (%s): %s", theme.key, len(items))
                return False
            stock.build_collage(items, d / "collage.mp4", (1920, 1080))
            if self.db.get_setting("make_shorts") == "1":
                stock.build_collage(items, d / "collage_v.mp4", (1080, 1920))
            photo = next((i.path for i in items if i.kind == "photo"), None)
            v = self.db.video(video_id)
            still = self._dir(f"track_{v['track_id']}") / "image.png"
            if photo:
                fireplace.cover(photo, (1920, 1080)).save(still)
            else:
                fireplace.still_frame(fireplace.Background("video", d / "collage.mp4"), still)
            self.db.update_track(v["track_id"], image_path=str(still))
            with self.db.tx() as c:
                for i in items:
                    c.execute("INSERT OR IGNORE INTO stock_used(provider_id, theme, used_at) VALUES (?, ?, ?)",
                              (i.provider_id, theme.key, iso(utcnow())))
            return True
        finally:
            shutil.rmtree(d / "stock", ignore_errors=True)

    def _daily_fireplace(self, video_id: int, rng: random.Random) -> str:
        """Tek parçalık video için şömine arka planı seç; kareyi parçanın görseli yap."""
        v = self.db.video(video_id)
        marker = self._dir(f"video_{video_id}") / "background.txt"
        prev = marker.read_text().strip() if marker.exists() else None
        bg = fireplace.pick_background(rng, avoid=prev)
        marker.write_text(bg.name)
        img = fireplace.still_frame(bg, self._dir(f"track_{v['track_id']}") / "image.png")
        self.db.update_track(v["track_id"], image_path=str(img))
        return self.FIRE_SCENE

    def _fire_volume(self) -> int:
        raw = self.db.get_setting("fire_volume")
        return int(raw) if raw else 0

    def _video_audio(self, video_id: int, track_audio: Path) -> Path:
        """Şömine modunda parçanın altına çıtırtı ekle (kütüphanedeki parça temiz kalır)."""
        if not self._background(video_id) or self._fire_volume() <= 0:
            return track_audio
        out = self._dir(f"video_{video_id}") / "audio.mp3"
        return media.add_bed(track_audio, fireplace.ambience_bed(), out, self._fire_volume() / 100,
                             soft=self.db.get_setting("soft_master") == "1")

    def _write_meta(self, video_id: int, style: Style, scene: str) -> None:
        v = self.db.video(video_id)
        t = self.db.track(v["track_id"])
        theme = THEME_BY_KEY.get(t["theme"] or "")
        meta = metadata.generate("daily", style, t["duration_sec"], scene, self.recent_titles(),
                                 extra=(f"Theme of this track: {EN_LABEL[theme.key]}." if theme else ""),
                                 theme_label=EN_LABEL[theme.key] if theme else "")
        self.db.update_track(t["id"], name=meta.track_name)
        credits = stock.credits_line() if self._collage(video_id) else ""
        self.db.update_video(video_id, title=meta.title,
                             description=metadata.full_description(meta.description, extra_links=credits),
                             tags=meta.tags, thumbnail_text=meta.thumbnail_text)

    def _render_daily(self, video_id: int) -> None:
        v = self.db.video(video_id)
        t = self.db.track(v["track_id"])
        d = self._dir(f"video_{video_id}")
        bg = self._background(video_id)
        collage = self._collage(video_id)
        audio = self._video_audio(video_id, Path(t["audio_path"]))
        if collage:
            loop = collage
        elif bg:
            loop = fireplace.loop_for(bg, (1920, 1080))
        else:
            loop = media.make_loop(Path(t["image_path"]), d / "loop.mp4")
        out = media.mux(loop, audio, d / "video.mp4")
        if not bg and not collage:  # şömine döngüleri önbellekte, kolaj klasörde kalır
            loop.unlink(missing_ok=True)
        thumb = visuals.make_thumbnail(Path(t["image_path"]), d / "thumb.jpg", v["thumbnail_text"] or "FOCUS",
                                       STYLE_BY_KEY[v["style_key"]].label)
        preview = media.make_preview(audio, d / "preview.mp3")
        self.db.update_video(video_id, video_path=str(out), thumb_path=str(thumb), preview_path=str(preview))

    def _make_short(self, parent_id: int) -> int:
        parent = self.db.video(parent_id)
        for old in self.db.children(parent_id):
            self.db.update_video(old["id"], status="rejected")
        length = min(59, self.db.get_int("short_seconds"))
        if parent["track_id"]:
            t = self.db.track(parent["track_id"])
            audio, image, track_name = Path(t["audio_path"]), Path(t["image_path"]), t["name"]
            with_bed = CONFIG.media_dir / f"video_{parent_id}" / "audio.mp3"
            if self._background(parent_id) and with_bed.exists():
                audio = with_bed  # Short'ta da çıtırtı olsun
            start = max(0.0, min(t["duration_sec"] * 0.3, t["duration_sec"] - length - 1))
        else:  # uzun mix: ikinci parçanın (yoksa ilkinin) içinden bir kesit
            pd = CONFIG.media_dir / f"video_{parent_id}"
            audio, image = pd / "mix.mp3", pd / "image.png"
            rows = self.db.query("SELECT ct.start_sec, t.name FROM compilation_tracks ct JOIN tracks t "
                                 "ON t.id = ct.track_id WHERE ct.video_id = ? ORDER BY ct.position LIMIT 2",
                                 (parent_id,))
            pick = rows[-1] if rows else None
            track_name = pick["name"] if pick else None
            start = min((pick["start_sec"] if pick else 0.0) + 25.0, max(0.0, media.duration(audio) - length - 1))
        short_id = self.db.add_video(kind="short", track_id=parent["track_id"], parent_id=parent_id,
                                     style_key=parent["style_key"], status="building")
        d = self._dir(f"video_{short_id}")
        seg = media.cut_segment(audio, d / "segment.mp3", start, length)
        bg = self._background(parent_id)
        vcollage = self._collage(parent_id, "v")
        if vcollage:
            loop, bg = vcollage, True  # bg=True: döngü dosyası silinmesin
        elif bg:
            loop = fireplace.loop_for(bg, (1080, 1920))
        else:
            vimg = visuals.vertical_from(image, d / "vertical.png")
            loop = media.make_loop(vimg, d / "loop.mp4", size=(1080, 1920))
        out = media.mux(loop, seg, d / "video.mp4")
        seg.unlink(missing_ok=True)
        if not bg:
            loop.unlink(missing_ok=True)
        title = f"{(parent['title'] or 'Music')[:80]} #shorts"
        what = "full version" if parent["kind"] == "daily" else f"full {media.fmt_long(media.duration(audio))} mix"
        desc = metadata.full_description(
            f"{track_name or 'This track'} — {what} on the channel.\n\n{(parent['description'] or '')[:400]}")
        self.db.update_video(short_id, title=title, description=desc, tags=tags_of(parent),
                             video_path=str(out), status="pending")
        return short_id

    # --------------------------------------------------------------- regenerate
    def regenerate(self, video_id: int, part: str, progress: Progress = _noop) -> None:
        """part: music | image | meta"""
        v = self.db.video(video_id)
        style = STYLE_BY_KEY.get(v["style_key"] or "", active_styles()[0])
        rng = random.Random()
        if v["kind"] in LONG_KINDS:
            if part == "music":
                raise ValueError("Uzun videoda müzik yenilenmez; reddedip /uret ya da /derleme ile yeniden oluşturun. "
                                 "Reddedilen mixin parçaları bir sonraki mixte yeniden kullanılır.")
            if part == "image":
                progress("🖼 Yeni görsel hazırlanıyor")
                self._compilation_visuals(video_id, style, rng)
            else:
                progress("✍️ Metin yeniden yazılıyor")
                self._compilation_meta(video_id, style)
            return
        if part == "music":
            t = self.db.track(v["track_id"])
            self.db.update_track(t["id"], prompt=build_music_prompt(style, rng))
            progress("🎵 Müzik yeniden üretiliyor")
            self._make_track_audio(t["id"], int(t["duration_sec"] or self.db.get_int("daily_min_sec")))
        elif part == "image":
            self._daily_visuals(video_id, style, rng, progress)
        elif part == "meta":
            progress("✍️ Metin yeniden yazılıyor")
            theme = self._theme_of(video_id)
            self._write_meta(video_id, style, theme.scene if theme else
                             (self.FIRE_SCENE if self._background(video_id) else style.scenes[0]))
        progress("🎬 Video yeniden render ediliyor")
        self._render_daily(video_id)
        if self.db.get_setting("make_shorts") == "1" and part != "meta":
            self._make_short(video_id)

    # --------------------------------------------------------------- compilation
    def select_compilation_tracks(self, now: datetime | None = None) -> list[dict]:
        """En çok dinlenen parçaları seç, sonra kulağa akıcı gelecek sırayla diz."""
        now = now or utcnow()
        every = self.db.get_int("compilation_every_days")
        max_sec = self.db.get_int("compilation_max_min") * 60
        rows = self.db.query(
            "SELECT t.*, v.views, v.likes, v.publish_at, v.created_at AS v_created FROM tracks t "
            "JOIN videos v ON v.track_id = t.id AND v.kind = 'daily' AND v.status IN ('published', 'scheduled') "
            "WHERE t.audio_path IS NOT NULL")
        recently_used = {r["track_id"] for r in self.db.query(
            "SELECT ct.track_id FROM compilation_tracks ct JOIN videos v ON v.id = ct.video_id "
            "WHERE v.status IN ('pending', 'scheduled', 'published') "
            "AND v.id IN (SELECT id FROM videos WHERE kind = 'compilation' ORDER BY id DESC LIMIT 2)")}

        scored = []
        for r in rows:
            if not Path(r["audio_path"]).exists():
                continue
            published = parse_iso(r["publish_at"]) or parse_iso(r["v_created"]) or now
            age_days = max(1.0, (now - published).total_seconds() / 86400)
            score = (r["views"] + 5 * r["likes"]) / age_days ** 0.5  # yaşa göre normalize popülerlik
            fresh = age_days <= every + 1
            scored.append({"id": r["id"], "style_key": r["style_key"], "name": r["name"],
                           "duration": r["duration_sec"], "audio_path": r["audio_path"],
                           "score": score, "fresh": fresh, "used": r["id"] in recently_used})

        # Önce son dönemin parçaları, sonra daha önce derlemeye girmemiş eski hitler.
        scored.sort(key=lambda x: (not x["fresh"], x["used"], -x["score"]))
        chosen, total = [], 0.0
        repeat = self.db.get_setting("compilation_fill") == "repeat"
        for s in scored:
            if s["used"] and not s["fresh"] and not repeat:
                continue
            if total + s["duration"] > max_sec:
                continue
            chosen.append(s)
            total += s["duration"] - 6
        return order_for_flow(chosen)

    def create_compilation(self, progress: Progress = _noop) -> int:
        rng = random.Random()
        min_sec = self.db.get_int("compilation_min_min") * 60
        x = float(self.db.get_setting("mix_crossfade_sec") or 6)
        chosen = self.select_compilation_tracks()
        total = sum(c["duration"] - x for c in chosen)

        if total < min_sec and self.db.get_setting("compilation_fill") == "repeat":
            # Kredisiz: en çok dinlenenler sırasıyla tekrar edilerek hedef süreye tamamlanır.
            if not chosen:
                raise ValueError("Derlenecek yayınlanmış parça yok; önce birkaç parça videosu yayınlanmalı.")
            lo = min_sec
            hi = max(lo, self.db.get_int("compilation_max_min") * 60)
            target = rng.randint(lo, hi)
            base = list(chosen)
            if len(base) > 2 and base[0]["id"] == base[-1]["id"]:
                base = base[1:] + base[:1]
            while total < target:
                for c in base:
                    if total >= target:
                        break
                    chosen.append(dict(c))
                    total += c["duration"] - x
            progress(f"🔁 {len(base)} parça tekrarlanarak {media.fmt_long(total)} derleme hazırlanıyor (kredisiz)")
        elif total < min_sec:  # yeterli parça yoksa en başarılı stilde ek "exclusive" parça üret
            perf = self.style_performance()
            style = STYLE_BY_KEY[max(perf, key=perf.get)] if perf else rng.choice(active_styles())
            while total < min_sec:
                dur = min(self.db.get_int("daily_max_sec"), int(min_sec - total) + 30)
                dur = max(dur, self.db.get_int("daily_min_sec"))
                progress(f"🎵 Derleme için ek parça üretiliyor ({style.label}, {dur // 60} dk)")
                tid = self.db.add_track(style_key=style.key, prompt=build_music_prompt(style, rng), exclusive=1,
                                        name=f"Exclusive {len(chosen) + 1}")
                self._make_track_audio(tid, dur)
                t = self.db.track(tid)
                chosen.append({"id": tid, "style_key": style.key, "name": t["name"], "duration": t["duration_sec"],
                               "audio_path": t["audio_path"], "score": 0.0, "fresh": True, "used": False})
                total += t["duration_sec"] - x
            chosen = order_for_flow(chosen)

        styles = [c["style_key"] for c in chosen]
        main_style = STYLE_BY_KEY[max(set(styles), key=styles.count)]
        video_id = self.db.add_video(kind="compilation", style_key=main_style.key, status="building")
        try:
            progress(f"🎚 {len(chosen)} parça crossfade ile birleştiriliyor")
            d = self._dir(f"video_{video_id}")
            vol = self._fire_volume() if self.fireplace_on() else 0
            bed = fireplace.ambience_bed() if vol > 0 else None
            starts = media.crossfade_concat([Path(c["audio_path"]) for c in chosen], d / "mix.mp3", xfade=x,
                                            bed=bed, bed_volume=vol / 100)
            with self.db.tx() as c:
                for pos, (ch, st) in enumerate(zip(chosen, starts)):
                    c.execute("INSERT INTO compilation_tracks(video_id, track_id, position, start_sec) "
                              "VALUES (?, ?, ?, ?)", (video_id, ch["id"], pos, st))
            progress("🖼 Görsel hazırlanıyor")
            self._compilation_visuals(video_id, main_style, rng, render=False)
            progress("✍️ Başlık, açıklama ve zaman damgaları yazılıyor")
            self._compilation_meta(video_id, main_style)
            progress("🎬 Uzun video render ediliyor (birkaç dakika sürebilir)")
            self._compilation_render(video_id)
            self.db.update_video(video_id, status="pending")
        except Exception as e:
            self.db.update_video(video_id, status="failed", error=str(e)[:1000])
            raise
        return video_id

    def fireplace_on(self) -> bool:
        return self.db.get_setting("fireplace") == "1" and bool(fireplace.backgrounds())

    def _background(self, video_id: int) -> fireplace.Background | None:
        """Bu video için seçilmiş şömine arka planı (yoksa None = normal görsel)."""
        f = CONFIG.media_dir / f"video_{video_id}" / "background.txt"
        return fireplace.find_background(f.read_text().strip()) if f.exists() else None

    def _compilation_visuals(self, video_id: int, style: Style, rng: random.Random, render: bool = True) -> None:
        d = self._dir(f"video_{video_id}")
        marker = d / "background.txt"
        if self.fireplace_on():
            prev = marker.read_text().strip() if marker.exists() else None
            bg = fireplace.pick_background(rng, avoid=prev)
            marker.write_text(bg.name)
            fireplace.still_frame(bg, d / "image.png")
        else:
            marker.unlink(missing_ok=True)
            visuals.generate_image(build_image_prompt(style, rng=rng), d / "image.png", "16:9",
                                   seed=rng.randint(1, 2**31))
        if render:
            self._compilation_render(video_id)

    def _compilation_tracklist(self, video_id: int) -> tuple[str, float]:
        rows = self.db.query(
            "SELECT ct.start_sec, t.name, t.style_key FROM compilation_tracks ct JOIN tracks t ON t.id = ct.track_id "
            "WHERE ct.video_id = ? ORDER BY ct.position", (video_id,))
        lines = [f"{media.fmt_ts(r['start_sec'])} {r['name'] or STYLE_BY_KEY[r['style_key']].label}" for r in rows]
        mix = CONFIG.media_dir / f"video_{video_id}" / "mix.mp3"
        return "\n".join(lines), media.duration(mix)

    def _compilation_meta(self, video_id: int, style: Style) -> None:
        tracklist, total = self._compilation_tracklist(video_id)
        kind = self.db.video(video_id)["kind"]
        n = tracklist.count("\n") + 1
        extra = ("This is a curated mix of the channel's most listened recent tracks." if kind == "compilation"
                 else f"One continuous {media.fmt_long(total)} mix of {n} tender romantic piano pieces, "
                      "smoothly crossfaded, no ads or interruptions inside the music.")
        scene = style.scenes[0]
        if self._background(video_id):
            scene = "a cozy wood fireplace burning at night, warm flickering flames and glowing embers"
            if self.db.get_setting("fire_volume") not in ("", "0"):
                extra += " Soft crackling fireplace sounds play gently under the music."
        meta = metadata.generate(kind, style, total, scene, self.recent_titles(), extra=extra)
        desc = metadata.full_description(meta.description, tracklist)
        self.db.update_video(video_id, title=meta.title, description=desc, tags=meta.tags,
                             thumbnail_text=meta.thumbnail_text)
        v = self.db.video(video_id)
        if v["video_path"]:  # yalnızca metin değiştiyse küçük resmi güncelle
            self._compilation_thumb(video_id)

    def _compilation_thumb(self, video_id: int) -> Path:
        v = self.db.video(video_id)
        d = self._dir(f"video_{video_id}")
        _, total = self._compilation_tracklist(video_id)
        style = STYLE_BY_KEY.get(v["style_key"] or "", active_styles()[0])
        sub = media.fmt_long(total).upper() + (" MIX" if v["kind"] == "compilation" else "")
        thumb = visuals.make_thumbnail(d / "image.png", d / "thumb.jpg", v["thumbnail_text"] or style.thumb_word, sub)
        self.db.update_video(video_id, thumb_path=str(thumb))
        return thumb

    def _compilation_render(self, video_id: int) -> None:
        d = self._dir(f"video_{video_id}")
        bg = self._background(video_id)
        loop = fireplace.loop_for(bg, (1920, 1080)) if bg else media.make_loop(d / "image.png", d / "loop.mp4")
        out = media.mux(loop, d / "mix.mp3", d / "video.mp4")
        if not bg:  # şömine döngüleri önbellekte kalır, tekrar kullanılır
            loop.unlink(missing_ok=True)
        preview = media.make_preview(d / "mix.mp3", d / "preview.mp3", max_seconds=600)
        self.db.update_video(video_id, video_path=str(out), preview_path=str(preview))
        self._compilation_thumb(video_id)

    def daily_due(self, now: datetime | None = None) -> bool:
        """`daily_every_days` (varsayılan 1) geçtiyse yeni parça videosu zamanı."""
        now = now or utcnow()
        raw = self.db.get_setting("daily_every_days")
        every = int(raw) if raw else 1
        last = self.db.one("SELECT created_at FROM videos WHERE kind = 'daily' "
                           "AND status NOT IN ('rejected', 'failed') ORDER BY id DESC LIMIT 1")
        return not last or now - parse_iso(last["created_at"]) >= timedelta(days=every) - timedelta(hours=2)

    def compilation_due(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        every = self.db.get_int("compilation_every_days")
        last = self.db.one("SELECT created_at FROM videos WHERE kind = 'compilation' "
                           "AND status NOT IN ('rejected', 'failed') ORDER BY id DESC LIMIT 1")
        if last:
            return now - parse_iso(last["created_at"]) >= timedelta(days=every) - timedelta(hours=2)
        first = self.db.one("SELECT created_at FROM videos WHERE kind = 'daily' AND status IN "
                            "('scheduled', 'published') ORDER BY id LIMIT 1")
        return bool(first) and now - parse_iso(first["created_at"]) >= timedelta(days=every) - timedelta(hours=2)

    # ------------------------------------------------------------------ long mix
    def mix_due(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        every = self.db.get_int("mix_every_days")
        last = self.db.one("SELECT created_at FROM videos WHERE kind = 'mix' "
                           "AND status NOT IN ('rejected', 'failed') ORDER BY id DESC LIMIT 1")
        return not last or now - parse_iso(last["created_at"]) >= timedelta(days=every) - timedelta(hours=2)

    def library_tracks(self, style_key: str) -> tuple[list[dict], list[dict]]:
        """Bu stilde sesi duran parçalar: (hiç yayınlanmamış, yayınlanmış ve tekrar kullanılabilir).

        Hiç yayınlanmamışlar (yarıda kalan / reddedilen mixlerden) öncelikli ve sınırsız kullanılır.
        Yayınlanmışlar az kullanılandan çok kullanılana sıralanır; son 3 mixte geçenler atlanır.
        """
        busy: set[int] = set()
        published: dict[int, list[int]] = {}
        recent_mixes = {r["id"] for r in self.db.query(
            "SELECT id FROM videos WHERE kind = 'mix' AND status IN ('scheduled', 'published') "
            "ORDER BY id DESC LIMIT 3")}
        recent: set[int] = set()
        for r in self.db.query("SELECT ct.track_id, v.id vid, v.status, v.views FROM compilation_tracks ct "
                               "JOIN videos v ON v.id = ct.video_id"):
            if r["status"] in ("pending", "building", "uploading"):
                busy.add(r["track_id"])
            elif r["status"] in ("scheduled", "published"):
                published.setdefault(r["track_id"], []).append(r["views"])
                if r["vid"] in recent_mixes:
                    recent.add(r["track_id"])
        for r in self.db.query("SELECT track_id, status, views FROM videos WHERE kind = 'daily' "
                               "AND track_id IS NOT NULL"):
            if r["status"] in ("pending", "building", "uploading"):
                busy.add(r["track_id"])
            elif r["status"] in ("scheduled", "published"):
                published.setdefault(r["track_id"], []).append(r["views"])

        unused, reusable = [], []
        for t in self.db.query("SELECT * FROM tracks WHERE style_key = ? AND audio_path IS NOT NULL "
                               "AND duration_sec IS NOT NULL ORDER BY id", (style_key,)):
            if t["id"] in busy or not Path(t["audio_path"]).exists():
                continue
            item = {"id": t["id"], "style_key": t["style_key"], "name": t["name"], "duration": t["duration_sec"],
                    "audio_path": t["audio_path"], "score": float(sum(published.get(t["id"], [0]))),
                    "uses": len(published.get(t["id"], []))}
            if t["id"] not in published:
                unused.append(item)
            elif t["id"] not in recent:
                reusable.append(item)
        reusable.sort(key=lambda x: (x["uses"], -x["score"]))
        return unused, reusable

    def create_mix(self, style_key: str | None = None, progress: Progress = _noop,
                   minutes: int | None = None) -> int:
        """1 sa 20 dk – 3 sa+ uzunluğunda, tek stilde, çok parçalı kesintisiz mix üret.

        minutes verilirse hedef süre odur (ör. /demo için 10 dk)."""
        rng = random.Random()
        recent = [r["style_key"] for r in self.db.query(
            "SELECT style_key FROM videos WHERE kind = 'mix' ORDER BY id DESC LIMIT 5")]
        style = STYLE_BY_KEY[style_key] if style_key else pick_style(
            recent, self.style_performance(), rng, self.disabled_styles())
        lo, hi = sorted((self.db.get_int("mix_min_min"), self.db.get_int("mix_max_min")))
        target = (minutes or rng.randint(lo, hi)) * 60
        tlo, thi = sorted((self.db.get_int("daily_min_sec"), self.db.get_int("daily_max_sec")))
        x = float(self.db.get_setting("mix_crossfade_sec") or MIX_XFADE)

        try:  # render öncesi disk açılsın (5 GB volume)
            pruned = self.prune_library()
            if pruned:
                log.info("Mix öncesi %s eski parça sesi silindi", pruned)
        except Exception as e:  # noqa: BLE001
            log.warning("Kütüphane temizliği başarısız: %s", e)
        unused, reusable = self.library_tracks(style.key)
        fresh: list[dict] = []
        reused: list[dict] = []
        total = 0.0
        for t in unused:
            if total >= target:
                break
            fresh.append(t)
            total += t["duration"] - x
        cap, used_cap = target * self.db.get_int("mix_reuse_pct") / 100, 0.0
        for t in reusable:
            if total >= target:
                break
            if used_cap + t["duration"] > cap:
                continue
            reused.append(t)
            used_cap += t["duration"]
            total += t["duration"] - x

        video_id = self.db.add_video(kind="mix", style_key=style.key, status="building")
        try:
            avg = (tlo + thi) / 2 - x
            est = max(0, math.ceil((target - total) / avg)) if total < target else 0
            progress(f"💕 {style.label} · hedef {media.fmt_long(target)} · "
                     f"hazır {len(fresh) + len(reused)} parça, ~{est} yeni parça üretilecek")
            taken = {t["name"] for t in fresh + reused if t["name"]}
            n = 0
            while total < target:
                need = target - total + x
                if need <= thi:
                    dur = max(tlo, math.ceil(need))
                else:  # son parçaya en az bir tam parça kadar yer bırak
                    dur = rng.randint(tlo, max(tlo, min(thi, int(need - tlo))))
                n += 1
                if n == 1 or n % 5 == 0 or n == est:
                    progress(f"🎵 Parça {n}/~{max(est, n)} üretiliyor ({media.fmt_long(total)} hazır)")
                name = metadata.random_track_name(rng, taken)
                taken.add(name)
                tid = self.db.add_track(style_key=style.key, prompt=build_music_prompt(style, rng), exclusive=1,
                                        name=name)
                self._make_track_audio(tid, dur)
                t = self.db.track(tid)
                fresh.append({"id": tid, "style_key": style.key, "name": name, "duration": t["duration_sec"],
                              "audio_path": t["audio_path"], "score": 0.0, "uses": 0})
                total += t["duration_sec"] - x

            chosen = spread_in(fresh, reused)
            progress(f"🎚 {len(chosen)} parça crossfade ile birleştiriliyor ({media.fmt_long(total)})")
            d = self._dir(f"video_{video_id}")
            vol = self.db.get_int("fire_volume") if self.db.get_setting("fire_volume") else 0
            bed = None
            if vol > 0:
                progress("🔥 Ateş çıtırtısı sesi hazırlanıyor")
                bed = fireplace.ambience_bed()
            starts = media.crossfade_concat([Path(c["audio_path"]) for c in chosen], d / "mix.mp3", xfade=x,
                                            bed=bed, bed_volume=vol / 100)
            with self.db.tx() as c:
                for pos, (ch, st) in enumerate(zip(chosen, starts)):
                    c.execute("INSERT INTO compilation_tracks(video_id, track_id, position, start_sec) "
                              "VALUES (?, ?, ?, ?)", (video_id, ch["id"], pos, st))
            progress("🔥 Şömine arka planı seçiliyor" if self.fireplace_on() else "🖼 Görsel hazırlanıyor")
            self._compilation_visuals(video_id, style, rng, render=False)
            progress("✍️ Başlık, açıklama ve parça listesi yazılıyor")
            self._compilation_meta(video_id, style)
            progress("🎬 Uzun video render ediliyor (birkaç dakika sürebilir)")
            self._compilation_render(video_id)
            if self.db.get_setting("make_shorts") == "1":
                progress("📱 Short hazırlanıyor")
                self._make_short(video_id)
            self.db.update_video(video_id, status="pending")
        except Exception as e:
            self.db.update_video(video_id, status="failed", error=str(e)[:1000])
            raise
        return video_id

    def prune_library(self, now: datetime | None = None) -> int:
        """`library_keep_days`'ten eski parça seslerini sil (disk dolmasın). Silinen parça sayısını döndürür."""
        raw = self.db.get_setting("library_keep_days")
        if not raw or int(raw) <= 0:
            return 0
        cutoff = iso((now or utcnow()) - timedelta(days=int(raw)))
        busy = {r["track_id"] for r in self.db.query(
            "SELECT ct.track_id FROM compilation_tracks ct JOIN videos v ON v.id = ct.video_id "
            "WHERE v.status IN ('pending', 'building', 'uploading') UNION "
            "SELECT track_id FROM videos WHERE status IN ('pending', 'building', 'uploading') "
            "AND track_id IS NOT NULL")}
        n = 0
        for t in self.db.query("SELECT id FROM tracks WHERE audio_path IS NOT NULL AND created_at < ?", (cutoff,)):
            if t["id"] in busy:
                continue
            shutil.rmtree(CONFIG.media_dir / f"track_{t['id']}", ignore_errors=True)
            self.db.update_track(t["id"], audio_path=None, image_path=None)
            n += 1
        return n

    # ------------------------------------------------------------------ upload
    def approve(self, video_id: int, progress: Progress = _noop) -> list[str]:
        """Videoyu (ve varsa Short'unu) YouTube'a yükle. Yüklenen YouTube id'lerini döndürür."""
        from .youtube import YouTube  # Google kütüphanesi testlerde gerekmesin

        v = self.db.video(video_id)
        children = [c for c in self.db.children(video_id) if c["status"] == "pending"]
        if v["status"] != "pending" and not children:
            raise ValueError(f"Video #{video_id} onay beklemiyor (durum: {v['status']})")
        items = []
        if v["status"] == "pending":
            publish_at = self.next_publish_at()
            items.append((v, publish_at))
        else:  # ana video önceden yüklendi, yalnızca Short kaldıysa
            publish_at = parse_iso(v["publish_at"])
        base = max(publish_at or utcnow(), utcnow())
        for child in children:
            items.append((child, base + timedelta(hours=self.db.get_int("short_delay_hours"))))

        yt = None if CONFIG.dry_run else YouTube()
        ids: list[str] = []
        for row, when in items:
            self.db.update_video(row["id"], status="uploading")
            try:
                progress(f"⬆️ Yükleniyor: {row['title']}")
                if yt is None:
                    yid = f"dryrun-{row['id']}"
                else:
                    yid = yt.upload(Path(row["video_path"]), row["title"], row["description"], tags_of(row), when)
                    if row["thumb_path"]:
                        yt.set_thumbnail(yid, Path(row["thumb_path"]))
                    self._add_to_playlists(yt, row, yid)
                self.db.update_video(row["id"], youtube_id=yid, status="scheduled" if when else "published",
                                     publish_at=iso(when or utcnow()), error=None)
                ids.append(yid)
                self._cleanup_after_upload(row)
            except Exception as e:
                self.db.update_video(row["id"], status="pending", error=str(e)[:1000])
                raise
        return ids

    def _add_to_playlists(self, yt, row, yid: str) -> None:
        prof = profiles.current()
        style_list = STYLE_BY_KEY[row["style_key"]].label + prof.style_playlist_suffix if row["style_key"] else None
        names = {"daily": [style_list], "compilation": [prof.long_playlist],
                 "mix": [prof.long_playlist, style_list], "short": []}
        for name in names.get(row["kind"], []):
            if not name:
                continue
            key = f"playlist:{name}"
            pid = self.db.get_setting(key)
            if not pid:
                pid = yt.ensure_playlist(name, f"{name} — {profiles.channel_name()}")
                self.db.set_setting(key, pid)
            yt.add_to_playlist(pid, yid)

    def _cleanup_after_upload(self, row) -> None:
        """Yüklenen mp4'leri sil (yer kazanmak için); ses ve görseller derleme için kalır."""
        if row["video_path"]:
            Path(row["video_path"]).unlink(missing_ok=True)
        if row["kind"] == "short":
            shutil.rmtree(CONFIG.media_dir / f"video_{row['id']}", ignore_errors=True)
        if row["kind"] == "daily":
            for f in ("collage.mp4", "collage_v.mp4", "audio.mp3"):
                (CONFIG.media_dir / f"video_{row['id']}" / f).unlink(missing_ok=True)
        if row["kind"] in LONG_KINDS:
            (CONFIG.media_dir / f"video_{row['id']}" / "mix.mp3").unlink(missing_ok=True)

    def reject(self, video_id: int) -> None:
        for row in [self.db.video(video_id), *self.db.children(video_id)]:
            self.db.update_video(row["id"], status="rejected")
            if row["video_path"]:
                Path(row["video_path"]).unlink(missing_ok=True)
            if row["kind"] in LONG_KINDS:  # parçalar kütüphanede kalır, büyük mix dosyası silinir
                (CONFIG.media_dir / f"video_{row['id']}" / "mix.mp3").unlink(missing_ok=True)

    # ------------------------------------------------------------------ stats
    def refresh_stats(self) -> int:
        if CONFIG.dry_run:
            return 0
        from .youtube import YouTube

        rows = self.db.query("SELECT id, youtube_id, status, publish_at FROM videos "
                             "WHERE youtube_id IS NOT NULL AND status IN ('scheduled', 'published')")
        if not rows:
            return 0
        stats = YouTube().stats([r["youtube_id"] for r in rows])
        now = utcnow()
        for r in rows:
            s = stats.get(r["youtube_id"])
            if not s:
                continue
            status = r["status"]
            pub = parse_iso(r["publish_at"])
            if status == "scheduled" and pub and pub <= now and s["privacy"] == "public":
                status = "published"
            self.db.update_video(r["id"], views=s["views"], likes=s["likes"], privacy=s["privacy"],
                                 status=status, stats_updated_at=iso(now))
        return len(rows)

    def locked_private(self) -> list:
        """Yayın zamanı geçtiği halde hâlâ 'private' olanlar: API denetimi (audit) yapılmamış olabilir."""
        now = utcnow()
        return [r for r in self.db.query(
            "SELECT * FROM videos WHERE status = 'scheduled' AND privacy = 'private' AND youtube_id IS NOT NULL")
            if parse_iso(r["publish_at"]) and parse_iso(r["publish_at"]) < now - timedelta(hours=2)]


def order_for_flow(tracks: list[dict]) -> list[dict]:
    """En popüler parçayla başla, sonra enerji seviyesi en yakın parçayla devam et (yumuşak geçişler)."""
    if len(tracks) <= 2:
        return list(tracks)
    remaining = sorted(tracks, key=lambda x: -x["score"])
    order = [remaining.pop(0)]
    while remaining:
        cur = STYLE_BY_KEY[order[-1]["style_key"]].energy
        nxt = min(remaining, key=lambda x: (abs(STYLE_BY_KEY[x["style_key"]].energy - cur),
                                            x["style_key"] == order[-1]["style_key"], -x["score"]))
        remaining.remove(nxt)
        order.append(nxt)
    return order


def spread_in(base: list[dict], extra: list[dict]) -> list[dict]:
    """`extra` parçalarını `base` içine eşit aralıklarla yerleştir (tekrar kullanılanlar dağılsın)."""
    out = list(base)
    if not extra:
        return out
    step = (len(base) + len(extra)) / (len(extra) + 1)
    for i, e in enumerate(extra, 1):
        out.insert(min(len(out), round(step * i)), e)
    return out
