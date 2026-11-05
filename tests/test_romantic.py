"""Romantic profili: 1 sa 20 dk – 3 sa+ uzun mixler (testte süreler küçültülür)."""
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import media, profiles
from app.bot import validate_setting
from app.db import Database, iso
from app.metadata import fallback, full_description
from app.pipeline import Pipeline, spread_in
from app.styles import ROMANTIC_STYLES, active_styles, build_image_prompt, build_music_prompt, pick_style
from tests.test_pipeline import FakeMusic


@pytest.fixture(autouse=True)
def romantic():
    profiles.set_active("romantic")
    yield
    profiles.set_active(None)


@pytest.fixture
def pipe(tmp_path, monkeypatch):
    db = Database(tmp_path / "r.db")
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    monkeypatch.setattr("app.media.LOOP_SECONDS", 2)
    db.set_setting("daily_min_sec", "60")   # FakeMusic en fazla 20 sn üretir -> parça ~14 sn katkı
    db.set_setting("daily_max_sec", "60")
    db.set_setting("mix_min_min", "1")
    db.set_setting("mix_max_min", "1")
    return Pipeline(db)


def test_defaults_short_tracks_and_long_compilations(tmp_path):
    db = Database(tmp_path / "d.db")
    assert profiles.current().main_kind == "daily"
    assert db.get_int("daily_every_days") == 3
    assert 270 <= db.get_int("daily_min_sec") <= db.get_int("daily_max_sec") <= 330
    assert db.get_int("compilation_every_days") == 7
    assert db.get_int("compilation_min_min") == 120 and db.get_int("compilation_max_min") == 180
    assert db.get_int("sleep_compilation_min_min") == 180 and db.get_int("compilation_min_tracks") == 6
    assert db.get_setting("compilation_fill") == "repeat"


def test_styles_and_prompts_are_romantic_piano():
    from app.series import SERIES_BY_KEY
    assert active_styles() == ROMANTIC_STYLES
    rng = random.Random(2)
    s = pick_style([], {}, rng)
    assert s in ROMANTIC_STYLES
    for st in [x for x in ROMANTIC_STYLES if x.key in SERIES_BY_KEY["romance"].styles]:
        p = build_music_prompt(st, rng)
        assert "piano" in p.lower() and "No vocals" in p and "romantic" in p.lower()
    assert "romantic" in build_image_prompt(ROMANTIC_STYLES[0], rng=rng).lower()


def test_fallback_title_mentions_hours():
    m = fallback("mix", ROMANTIC_STYLES[0], 3 * 3600 + 60, random.Random(0))
    assert "3 Hours" in m.title
    m = fallback("mix", ROMANTIC_STYLES[0], 85 * 60, random.Random(0))
    assert "1 Hour 25 Min" in m.title
    assert "#RomanticMusic" in full_description(m.description)


def test_fmt_long():
    assert media.fmt_long(45 * 60) == "45 Min"
    assert media.fmt_long(80 * 60) == "1 Hour 20 Min"
    assert media.fmt_long(181 * 60) == "3 Hours"


def test_validate_mix_settings():
    assert validate_setting("mix_max_min", "200") is None
    assert validate_setting("mix_min_min", "10")
    assert validate_setting("mix_reuse_pct", "90")


def test_spread_in():
    base = [{"id": i} for i in range(6)]
    out = spread_in(base, [{"id": "a"}, {"id": "b"}])
    assert len(out) == 8 and out[0]["id"] == 0 and out[-1]["id"] == 5
    assert {out.index({"id": "a"}), out.index({"id": "b"})} == {3, 5}


def test_mix_end_to_end(pipe):
    db = pipe.db
    vid = pipe.create_mix(ROMANTIC_STYLES[0].key)
    v = db.video(vid)
    assert v["kind"] == "mix" and v["status"] == "pending"
    rows = db.query("SELECT * FROM compilation_tracks WHERE video_id = ? ORDER BY position", (vid,))
    assert len(rows) >= 4
    assert media.duration(Path(v["video_path"])) >= 60
    assert "Tracklist" in v["description"] and "00:00" in v["description"]
    names = [db.track(r["track_id"])["name"] for r in rows]
    assert len(set(names)) == len(names)  # her parçanın ayrı adı var
    assert len(db.children(vid)) == 1  # Short

    ids = pipe.approve(vid)
    assert len(ids) == 2 and db.video(vid)["status"] in ("scheduled", "published")
    assert not (Path(v["video_path"]).parent / "mix.mp3").exists()
    assert not pipe.mix_due()


def test_rejected_mix_tracks_are_reused_for_free(pipe, monkeypatch):
    db = pipe.db
    calls = []

    class Counting(FakeMusic):
        def compose(self, prompt, duration_sec, out_path):
            calls.append(duration_sec)
            return super().compose(prompt, duration_sec, out_path)

    monkeypatch.setattr("app.pipeline.get_provider", lambda: Counting())
    first = pipe.create_mix(ROMANTIC_STYLES[1].key)
    made = len(calls)
    pipe.reject(first)
    second = pipe.create_mix(ROMANTIC_STYLES[1].key)
    assert len(calls) == made  # ikinci mix için yeni müzik üretilmedi
    a = {r["track_id"] for r in db.query("SELECT track_id FROM compilation_tracks WHERE video_id = ?", (first,))}
    b = {r["track_id"] for r in db.query("SELECT track_id FROM compilation_tracks WHERE video_id = ?", (second,))}
    assert a == b


def test_reuse_respects_cap_and_prune(pipe):
    db = pipe.db
    first = pipe.create_mix(ROMANTIC_STYLES[2].key)
    pipe.approve(first)
    db.update_video(first, status="published", views=50)
    unused, reusable = pipe.library_tracks(ROMANTIC_STYLES[2].key)
    assert not unused and not reusable  # son 3 mixte kullanılanlar hemen tekrar edilmez

    old = iso(datetime.now(timezone.utc) - timedelta(days=200))
    with db.tx() as c:
        c.execute("UPDATE tracks SET created_at = ?", (old,))
    assert pipe.prune_library() == 0  # varsayılan 0 = parçalar derlemeler için hep saklanır
    db.set_setting("library_keep_days", "30")
    assert pipe.prune_library() > 0
    assert db.one("SELECT COUNT(*) n FROM tracks WHERE audio_path IS NOT NULL")["n"] == 0


def test_prompts_are_soft_spa_style_without_bright_instruments():
    from app.series import SERIES_BY_KEY
    rng = random.Random(5)
    bright = ("glockenspiel", "celesta", "bells", "harp", "bright grand")
    romance = [st for st in ROMANTIC_STYLES if st.key in SERIES_BY_KEY["romance"].styles]
    for st in romance:
        assert st.bpm[1] <= 70
        assert not any(b in " ".join(st.instruments).lower() for b in bright)
        p = build_music_prompt(st, rng)
        assert "spa and massage" in p and "No bright, thin, piercing or high-pitched notes" in p


def test_soft_master_applied_and_crossfade_setting(tmp_path):
    db = Database(tmp_path / "s.db")
    assert db.get_setting("soft_master") == "1" and db.get_int("mix_crossfade_sec") == 12
    src = tmp_path / "a.mp3"
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=6000:duration=20", str(src)],
                   check=True, capture_output=True)
    hard = media.master_audio(src, tmp_path / "h.mp3")
    soft = media.master_audio(src, tmp_path / "s.mp3", fade_in=5, fade_out=10, soft=True)
    assert media.duration(soft) == pytest.approx(media.duration(hard), abs=0.2)


def test_description_has_subscribe_link():
    d = full_description("Body")
    assert "https://www.youtube.com/@EvermoreRomancePiano?sub_confirmation=1" in d
    assert "Evermore Romance Piano" in d


def test_daily_with_fireplace_and_crackle_then_free_compilation(pipe, monkeypatch):
    db = pipe.db
    calls = []

    class Counting(FakeMusic):
        def compose(self, prompt, duration_sec, out_path):
            calls.append(duration_sec)
            return super().compose(prompt, duration_sec, out_path)

    monkeypatch.setattr("app.pipeline.get_provider", lambda: Counting())
    assert pipe.daily_due()
    ids = []
    for st in ROMANTIC_STYLES[:3]:
        vid = pipe.create_daily(st.key, auto=True)
        v = db.video(vid)
        assert pipe._background(vid) is not None                      # şömine arka planı
        assert (Path(v["video_path"]).parent / "audio.mp3").exists()  # çıtırtılı ses
        assert len(db.children(vid)) == 1
        pipe.approve(vid)
        db.update_video(vid, status="published", views=10)
        ids.append(vid)
    assert not pipe.daily_due()
    made = len(calls)

    db.set_setting("compilation_min_min", "1")
    db.set_setting("compilation_max_min", "1")
    db.set_setting("sleep_compilation_min_min", "1")
    db.set_setting("sleep_compilation_max_min", "1")
    db.set_setting("compilation_min_tracks", "2")
    cid = pipe.create_compilation()
    assert len(calls) == made  # derleme kredi harcamadı
    rows = db.query("SELECT track_id FROM compilation_tracks WHERE video_id = ?", (cid,))
    assert len(rows) > 3  # 3 parça tekrarlanarak 1 dk'ya tamamlandı
    c = db.video(cid)
    assert media.duration(Path(c["video_path"])) >= 60
    assert pipe._background(cid) is not None


def test_validate_new_settings():
    assert validate_setting("compilation_fill", "repeat") is None
    assert validate_setting("compilation_fill", "x")
    assert validate_setting("daily_every_days", "3") is None
    assert validate_setting("daily_every_days", "30")


def test_unused_tracks_become_videos_without_credits(pipe, monkeypatch):
    db = pipe.db
    # yarıda kalan bir mixin bıraktığı parça gibi: sesi var, hiçbir videoda yok
    tid = db.add_track(style_key=ROMANTIC_STYLES[0].key, prompt="p", exclusive=1, name="Moonlit Vow")
    pipe._make_track_audio(tid, 60)
    assert [t["id"] for t in pipe.unused_tracks()] == [tid]

    monkeypatch.setattr("app.pipeline.get_provider", lambda: (_ for _ in ()).throw(AssertionError("kredi")))
    vid = pipe.create_daily_from_track(tid)
    v = db.video(vid)
    assert v["status"] == "pending" and v["track_id"] == tid and Path(v["video_path"]).exists()
    assert pipe.unused_tracks() == []

    tid2 = db.add_track(style_key=ROMANTIC_STYLES[1].key, prompt="p", exclusive=1)
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    pipe._make_track_audio(tid2, 60)
    pipe.discard_track(tid2)
    assert pipe.unused_tracks() == []


def test_publish_rolls_to_next_morning(tmp_path):
    db = Database(tmp_path / "p.db")
    p = Pipeline(db)
    assert db.get_setting("publish_time") == "08:00"
    noon = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)        # İstanbul 12:00
    early = datetime(2026, 1, 5, 3, 0, tzinfo=timezone.utc)       # İstanbul 06:00
    assert p.next_publish_at(noon) == datetime(2026, 1, 6, 5, 0, tzinfo=timezone.utc)
    assert p.next_publish_at(early) == datetime(2026, 1, 5, 5, 0, tzinfo=timezone.utc)


def test_theme_picking_prefers_style_and_avoids_repeats():
    from app.themes import STYLE_THEMES, pick_theme
    rng = random.Random(1)
    picks = [pick_theme("rainy_romance_piano", ["rain", "autumn"], rng).key for _ in range(40)]
    assert "rain" not in picks and "autumn" not in picks
    assert sum(k in STYLE_THEMES["rainy_romance_piano"] for k in picks) > 10


def test_daily_uses_theme_collage_and_short(pipe, monkeypatch, tmp_path):
    import subprocess
    from app import stock

    def fake_fetch(theme, dest, used, rng):
        dest.mkdir(parents=True, exist_ok=True)
        items = []
        for n in range(3):
            pth = dest / f"v{n}.mp4"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration=10",
                            "-pix_fmt", "yuv420p", str(pth)], check=True, capture_output=True)
            items.append(stock.StockItem(f"v{n}", "video", pth))
        img = dest / "p0.jpg"
        from PIL import Image
        Image.new("RGB", (800, 450), (200, 120, 60)).save(img)
        items.append(stock.StockItem("p0", "photo", img))
        return items

    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch", fake_fetch)
    pipe.db.set_setting("daily_visual", "collage")
    monkeypatch.setattr(stock, "SEGMENT_SEC", 3.0)
    monkeypatch.setattr(stock, "XFADE_SEC", 0.5)
    db = pipe.db
    vid = pipe.create_daily(ROMANTIC_STYLES[0].key)
    v = db.video(vid)
    t = db.track(v["track_id"])
    assert t["theme"] and "Inspired by" in t["prompt"]
    assert pipe._collage(vid) and pipe._collage(vid, "v")
    assert pipe._background(vid) is None                   # kısa videoda şömine yok
    assert "Footage: Pexels" in v["description"]
    assert db.one("SELECT COUNT(*) n FROM stock_used")["n"] == 4
    short = db.children(vid)[0]
    from PIL import Image
    assert Path(short["video_path"]).exists()
    pipe.approve(vid)
    assert pipe._collage(vid) is None                      # yüklendikten sonra kolaj silinir


def test_manual_extras_choose_theme_and_do_not_shift_schedule(pipe):
    from app.themes import find_theme
    assert find_theme("sonbahar").key == "autumn" and find_theme("kar").key == "winter"
    assert find_theme("Deniz").key == "seaside" and find_theme("autumn").key == "autumn"
    assert find_theme("pizza") is None

    db = pipe.db
    auto = pipe.create_daily(ROMANTIC_STYLES[0].key, auto=True)
    assert not pipe.daily_due()
    manual = pipe.create_daily(ROMANTIC_STYLES[1].key, theme_key="winter")
    assert db.track(db.video(manual)["track_id"])["theme"] == "winter"
    old = iso(datetime.now(timezone.utc) - timedelta(days=4))
    db.update_video(auto, created_at=old)
    assert pipe.daily_due()  # yeni elle üretilen video takvimi kaydırmadı


def test_publish_now_skips_schedule(pipe):
    db = pipe.db
    db.set_setting("publish_time", "23:59")
    vid = pipe.create_daily(ROMANTIC_STYLES[0].key)
    pipe.approve(vid, publish_now=True)
    assert db.video(vid)["status"] == "published"


def test_used_tracks_sorted_by_views(pipe):
    db = pipe.db
    ids = []
    for n, views in enumerate((5, 120, 40)):
        vid = pipe.create_daily(ROMANTIC_STYLES[n].key)
        pipe.approve(vid)
        db.update_video(vid, status="published", views=views, likes=views // 10)
        ids.append(vid)
    pending = pipe.create_daily(ROMANTIC_STYLES[3].key)
    rows = pipe.used_tracks()
    assert [r["views"] for r in rows[:3]] == [120, 40, 5]
    assert rows[-1]["vid"] == pending and rows[-1]["status"] == "pending"
    assert pipe.unused_tracks() == []


def test_single_scene_video_and_title_format(pipe, monkeypatch):
    import subprocess
    from app import stock
    from app.themes import SCENES

    def fake_scene(queries, dest, used, rng):
        dest.mkdir(parents=True, exist_ok=True)
        pth = dest / "v99.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=14",
                        "-pix_fmt", "yuv420p", str(pth)], check=True, capture_output=True)
        return stock.StockItem("v99", "video", pth)

    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch_scene", fake_scene)
    monkeypatch.setattr(stock, "fetch", lambda *a: [])
    db = pipe.db
    vid = pipe.create_daily("fireside_love_ballad", theme_key="autumn", visual="scene")
    v = db.video(vid)
    assert (Path(v["video_path"]).parent / "visual.txt").read_text() == "scene"
    assert pipe._collage(vid) and pipe._collage(vid, "v")
    assert "Romantic Love Music by the Fire | Cozy Autumn Night Ambience" in v["title"]
    assert "Perfect for:" in v["description"] and "Footage: Pexels" in v["description"]
    prompt = db.track(v["track_id"])["prompt"]
    assert "ensemble" in prompt and "cello" in prompt

    # both: sahne sonrası sıradaki video kolaja geçer (kolaj yoksa yedeğe)
    assert db.get_setting("last_daily_visual") == "scene"


def test_short_title_and_description_are_clean():
    from app.metadata import shorten, short_title
    long = "Hold Me a Little Longer 🌙 Romantic Love Music by the Fire | Cozy Autumn Night Ambience"
    t = short_title(long)
    assert t == "Hold Me a Little Longer 🌙 Romantic Love Music by the Fire #shorts"
    assert len(short_title("word " * 40)) <= 100 and not short_title("word " * 40).split()[-2].startswith("wor…")
    assert shorten("one two three four", 12) == "one two…"


def test_short_links_to_full_video_and_follows_meta(pipe, monkeypatch):
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    vid = pipe.create_daily("fireside_love_ballad", theme_key="autumn")
    short = db.children(vid)[0]
    assert "#shorts" in short["title"] and " | " not in short["title"]
    assert pipe.FULL_LINK_TOKEN in short["description"] and "#Shorts" in short["description"]
    assert "Relaxing after a\n" not in short["description"]

    pipe.regenerate(vid, "meta")
    parent_head = db.video(vid)["title"].split(" | ")[0]
    assert db.video(short["id"])["title"].startswith(parent_head)

    class FakeYT:
        n = 0
        def upload(self, *a, **k):
            FakeYT.n += 1
            return f"yt{FakeYT.n}"
        def set_thumbnail(self, *a): pass
        def ensure_playlist(self, *a): return "pl"
        def add_to_playlist(self, *a): pass
    import app.pipeline as pl
    import dataclasses
    monkeypatch.setattr(pl, "CONFIG", dataclasses.replace(pl.CONFIG, dry_run=False))
    import app.youtube as ytmod
    monkeypatch.setattr(ytmod, "YouTube", FakeYT)
    pipe.approve(vid)
    desc = db.video(short["id"])["description"]
    assert "🎧 Full song: https://youtu.be/yt1" in desc and pipe.FULL_LINK_TOKEN not in desc


def test_every_series_has_valid_soft_styles_and_themes():
    from app.series import SERIES
    from app.styles import STYLE_BY_KEY
    from app.themes import SCENES, THEME_BY_KEY
    bright = ("glockenspiel", "celesta", "bells", "harp", "bright grand")
    rng = random.Random(3)
    for ser in SERIES:
        assert ser.styles and ser.themes and len(ser.perfect_for) >= 8
        for k in ser.styles:
            st = STYLE_BY_KEY[k]
            assert st.bpm[1] <= 86 and not any(b in " ".join(st.instruments).lower() for b in bright)
            p = build_music_prompt(st, rng, purpose=ser.purpose)
            assert "No vocals" in p and "No bright, thin, piercing" in p
        for t in ser.themes:
            assert t in THEME_BY_KEY and t in SCENES
    sleep = next(s for s in SERIES if s.key == "sleep")
    assert "no percussion" in sleep.purpose and all(STYLE_BY_KEY[k].bpm[1] <= 70 for k in sleep.styles)
    assert "swing" in next(s for s in SERIES if s.key == "jazz").purpose


def test_auto_videos_rotate_series_and_use_matching_styles(pipe):
    from app.series import SERIES_BY_KEY, find_series
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    seen = []
    for _ in range(5):
        vid = pipe.create_daily(auto=True)
        t = db.track(db.video(vid)["track_id"])
        seen.append(t["series"])
        ser = SERIES_BY_KEY[t["series"]]
        assert t["style_key"] in ser.styles and t["theme"] in ser.themes
        v = db.video(vid)
        assert ser.genre in v["title"] and ser.hashtags in v["description"]
    assert seen == ["romance", "jazz", "sleep", "relax", "romance"]
    assert find_series("caz").key == "jazz" and find_series("uyku").key == "sleep"

    manual = pipe.create_daily(series_key="sleep")
    assert db.track(db.video(manual)["track_id"])["series"] == "sleep"
    assert pipe.next_series().key == "jazz"  # elle üretim sırayı değiştirmez


def test_compilations_are_per_series(pipe):
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    for key in ("jazz", "jazz", "sleep", "sleep", "sleep"):
        vid = pipe.create_daily(series_key=key)
        pipe.approve(vid)
        db.update_video(vid, status="published", views=10)
    db.set_setting("compilation_min_min", "1")
    db.set_setting("compilation_max_min", "1")
    db.set_setting("sleep_compilation_min_min", "1")
    db.set_setting("sleep_compilation_max_min", "1")
    db.set_setting("compilation_min_tracks", "2")
    cid = pipe.create_compilation()
    c = db.video(cid)
    assert c["series"] == "jazz"                      # sıradaki (romance'ın 2 parçası yok) -> jazz
    rows = db.query("SELECT t.series FROM compilation_tracks ct JOIN tracks t ON t.id = ct.track_id "
                    "WHERE ct.video_id = ?", (cid,))
    assert {r["series"] for r in rows} == {"jazz"}
    assert "Cozy Jazz Music" in c["title"] and "#CozyJazz" in c["description"]
    pipe.reject(cid)
    cid2 = pipe.create_compilation()
    assert db.video(cid2)["series"] == "sleep"          # sonraki derleme diğer seriye geçer


def test_calm_stock_selection_and_slow_motion(tmp_path):
    import subprocess
    from app import stock
    files = [{"file_type": "video/mp4", "width": 1920, "height": 1080, "fps": 29.97, "link": "a"},
             {"file_type": "video/mp4", "width": 1920, "height": 1080, "fps": 59.94, "link": "b"},
             {"file_type": "video/mp4", "width": 3840, "height": 2160, "fps": 59.94, "link": "c"}]
    best = stock._best_file(files)
    assert best["link"] == "b"                                  # 1080p 60 fps tercih edilir
    assert stock.slow_factor(best) == 2.0 and stock.slow_factor(files[0]) == stock.SLOW_DEFAULT
    assert not stock._calm({"url": "https://www.pexels.com/video/sunset-timelapse-123/"})
    assert stock._calm({"url": "https://www.pexels.com/video/ocean-waves-slow-motion-9/"})

    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=60:duration=20",
                    "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    seg = stock._segment(stock.StockItem("v1", "video", src, 2.0), tmp_path / "seg.mp4", (640, 360))
    assert media.duration(seg) == pytest.approx(stock.SEGMENT_SEC, abs=0.2)  # 7 sn kaynak -> 14 sn ağır çekim
    slow = stock.slow_down(stock.StockItem("v1", "video", src, 2.0), tmp_path / "slow.mp4", max_out=30)
    assert media.duration(slow) == pytest.approx(30, abs=0.3)                # 15 sn kaynak -> 30 sn
    assert stock.SEGMENT_SEC >= 12 and stock.XFADE_SEC >= 2.5


def test_card_video_previews_follow_regenerated_visuals(pipe):
    import asyncio
    import os
    import time
    from app.bot import Bot
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    vid = pipe.create_daily(ROMANTIC_STYLES[0].key)
    v = db.video(vid)
    shorts = [c for c in db.children(vid) if c["status"] == "pending"]

    bot = Bot.__new__(Bot)  # Telegram'a bağlanmadan yalnızca önizleme mantığını dene
    bot.db, bot.pipe = db, pipe
    previews = asyncio.run(bot._video_previews(v, shorts))
    assert [label[0] for _, label in previews] == ["🎬", "📱"]
    main_prev = previews[0][0]
    assert media.duration(main_prev) <= 20.5 and main_prev.stat().st_size < 5_000_000
    first_mtime = main_prev.stat().st_mtime

    time.sleep(1.1)
    pipe.regenerate(vid, "image")                       # 🖼 Görsel: video yeniden render edilir
    v = db.video(vid)
    previews = asyncio.run(bot._video_previews(v, [c for c in db.children(vid) if c["status"] == "pending"]))
    assert previews[0][0].stat().st_mtime > first_mtime  # önizleme de yenilendi


def test_scene_is_default_and_falls_back_to_fireplace_not_collage(pipe, monkeypatch):
    from app import stock
    db = pipe.db
    assert db.get_setting("daily_visual") == "scene"
    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch_scene", lambda *a: None)            # uygun klip bulunamadı
    monkeypatch.setattr(stock, "fetch", lambda *a: (_ for _ in ()).throw(AssertionError("kolaj olmamalı")))
    vid = pipe.create_daily(series_key="romance", theme_key="picnic")
    assert pipe._background(vid) is not None and pipe._collage(vid) is None  # tek sahne: şömine döngüsü
    from app.themes import find_theme
    assert find_theme("piknik").key == "picnic"


def test_natural_turkish_words_in_uret():
    from app.series import find_series
    from app.themes import find_theme
    words = "jazz şömineli oda".split()
    assert find_series(words[0]).key == "jazz"
    assert find_theme(words[1]).key == "fireplace"
    assert find_theme(words[2]) is None and find_series(words[2]) is None   # 'oda' atlanır
    for w, key in [("yağmurlu", "rain"), ("karlı", "winter"), ("ormanda", "forest"), ("kafede", "cafe"),
                   ("Şömine", "fireplace"), ("piknik", "picnic"), ("denizde", "seaside")]:
        assert find_theme(w).key == key, w


def test_boost_two_publish_slots_without_collisions(pipe):
    db = pipe.db
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    db.set_setting("boost_until", tomorrow)
    assert pipe.boost_active()
    noon = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)   # İstanbul 12:00
    first = pipe.next_publish_at(noon)
    assert first.astimezone(pipe.tz).strftime("%H:%M") == "18:00"
    vid = pipe.create_daily(ROMANTIC_STYLES[0].key)
    db.update_video(vid, status="scheduled", publish_at=iso(first))                       # 18:00 doldu
    second = pipe.next_publish_at(noon)
    assert second.astimezone(pipe.tz).strftime("%H:%M") == "08:00" and second.date() > first.date()
    db.set_setting("boost_until", "")
    assert not pipe.boost_active()


def test_auto_daily_uses_unused_tracks_first(pipe, monkeypatch):
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    tid = db.add_track(style_key=ROMANTIC_STYLES[0].key, prompt="p", exclusive=1, name="Leftover")
    pipe._make_track_audio(tid, 60)
    calls = []
    monkeypatch.setattr("app.pipeline.get_provider", lambda: (calls.append(1), FakeMusic())[1])
    v1 = pipe.create_auto_daily()
    assert db.video(v1)["track_id"] == tid and db.video(v1)["source"] == "auto" and not calls  # kredisiz
    v2 = pipe.create_auto_daily()
    assert db.video(v2)["track_id"] != tid and calls                                         # sonra yeni


def test_boost_job_makes_two_per_day(pipe, monkeypatch):
    import asyncio
    from app.bot import Bot
    db = pipe.db
    db.set_setting("boost_until", (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d"))
    bot = Bot.__new__(Bot)
    bot.db, bot.pipe, bot.tz = db, pipe, pipe.tz
    made = []

    async def fake_auto():
        vid = pipe.create_daily(ROMANTIC_STYLES[0].key, auto=True)
        made.append(vid)
    bot.do_auto_daily = fake_auto
    bot.paused = lambda: False

    class Job:
        def __init__(self, slot): self.data = slot
    class Ctx:
        def __init__(self, slot): self.job = Job(slot)

    db.set_setting("daily_visual", "fireplace")
    asyncio.run(bot.job_daily(Ctx(0)))
    asyncio.run(bot.job_daily(Ctx(0)))   # aynı saat ikinci kez çalışırsa yeni video yok
    asyncio.run(bot.job_daily(Ctx(1)))   # ikinci saat
    assert len(made) == 2
    db.set_setting("boost_until", "")
    asyncio.run(bot.job_daily(Ctx(1)))   # yoğun dönem bitince ikinci saat çalışmaz
    assert len(made) == 2


def test_people_thumbnail_candidates_and_choice(pipe, monkeypatch):
    from PIL import Image
    from app import stock
    from app.themes import people_queries
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    asked = []

    def fake_photos(queries, dest, used, rng, n=3):
        asked.append(queries)
        dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(n):
            p = dest / f"p{i}.jpg"
            Image.new("RGB", (1600, 900), (180 + i * 20, 90, 120)).save(p)
            out.append(stock.StockItem(f"p{i}", "photo", p))
        return out

    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch_photos", fake_photos)
    vid = pipe.create_daily(series_key="jazz", theme_key="cafe")
    opts = pipe.thumb_options(vid)
    assert [int(p.stem.split("_")[1]) for p in opts] == [0, 1, 2, 3]
    assert db.video(vid)["thumb_path"].endswith("thumb_1.jpg")            # varsayılan: insanlı 1. aday
    assert asked[0] == people_queries("cafe", "jazz") and "woman" in asked[0][0]
    assert Image.open(opts[1]).size == (1280, 720)

    pipe.set_thumb(vid, 0)
    pipe.regenerate(vid, "meta")                                           # metin değişse de seçim korunur
    assert db.video(vid)["thumb_path"].endswith("thumb_0.jpg") and len(asked) == 1  # yeniden indirilmez
    assert db.one("SELECT COUNT(*) n FROM stock_used WHERE theme = 'thumb'")["n"] == 3

    db.set_setting("thumb_style", "scene")
    vid2 = pipe.create_daily(series_key="sleep")
    assert [int(p.stem.split("_")[1]) for p in pipe.thumb_options(vid2)] == [0]


def _frame_rgb(path, t):
    import subprocess
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                           "-vf", "scale=32:18", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True).stdout


def test_pingpong_loop_plays_forward_then_backward(tmp_path):
    import subprocess
    from app import stock
    src = tmp_path / "lake.mp4"   # renk zamanla değişen klip: ileri-geri kontrolü için
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "color=c=black:size=640x360:rate=30:duration=8,geq=r='X+T*25':g='Y':b='T*30'",
                    "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    out = stock.pingpong_loop(src, tmp_path / "pp.mp4", (640, 360))
    total = media.duration(out)
    assert total == pytest.approx(16, abs=0.5)                     # ileri 8 + geri 8
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True, text=True)
    assert dec.stderr.strip() == ""
    a, b = _frame_rgb(out, 2.0), _frame_rgb(out, total - 2.0)      # simetrik anlar aynı kare olmalı
    diff = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
    assert diff < 12
    c = _frame_rgb(out, 6.0)
    assert sum(abs(x - y) for x, y in zip(a, c)) / len(a) > diff   # ama ileri giderken görüntü değişiyor


def test_scene_mode_by_theme(pipe, monkeypatch):
    import subprocess
    from app import stock
    db = pipe.db
    monkeypatch.setattr(pipe, "SCENE_SHOT_SEC", 4.0)
    monkeypatch.setattr(pipe, "SCENE_SHOT_XFADE", 1.0)

    def clip(dest, name, color):
        dest.mkdir(parents=True, exist_ok=True)
        p = dest / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:size=640x360:rate=30:duration=8",
                        "-pix_fmt", "yuv420p", str(p)], check=True, capture_output=True)
        return stock.StockItem(name, "video", p, 1.0)

    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch_scene", lambda q, dest, used, rng: clip(dest, "v1", "blue"))
    monkeypatch.setattr(stock, "fetch_scene_clips",
                        lambda q, dest, used, rng, n=3: [clip(dest, f"s{i}", c) for i, c in enumerate(("red", "green"))])
    monkeypatch.setattr(stock, "fetch_photos", lambda *a, **k: [])

    lake = pipe.create_daily(series_key="romance", theme_key="lake")             # geriye doğal: bumerang
    d = Path(db.video(lake)["video_path"]).parent
    assert (d / "scene_loop.txt").read_text() == "pingpong"
    rain = pipe.create_daily(series_key="romance", theme_key="rain")             # yağmur: çoklu çekim
    d2 = Path(db.video(rain)["video_path"]).parent
    assert (d2 / "scene_loop.txt").read_text() == "sequence"
    assert {r["provider_id"] for r in db.query("SELECT provider_id FROM stock_used")} >= {"v1", "s0", "s1"}


def test_long_videos_wait_for_enough_distinct_tracks(pipe):
    db = pipe.db
    db.set_setting("daily_visual", "fireplace")
    for _ in range(3):
        vid = pipe.create_daily(series_key="jazz")
        pipe.approve(vid)
        db.update_video(vid, status="published", views=5)
    assert not pipe.compilation_ready()                      # 3 < 6 farklı parça: otomatik derleme bekler
    with pytest.raises(ValueError, match="farklı parça"):
        pipe.create_compilation()
    assert pipe.compilation_range("sleep") == (180 * 60, 240 * 60)
    assert pipe.compilation_range("jazz") == (120 * 60, 180 * 60)
    db.set_setting("compilation_min_tracks", "3")
    assert pipe.compilation_ready()
