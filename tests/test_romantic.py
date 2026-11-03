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
    assert db.get_int("compilation_every_days") == 15
    assert db.get_int("compilation_min_min") == 80 and db.get_int("compilation_max_min") == 180
    assert db.get_setting("compilation_fill") == "repeat"


def test_styles_and_prompts_are_romantic_piano():
    assert active_styles() == ROMANTIC_STYLES
    rng = random.Random(2)
    s = pick_style([], {}, rng)
    assert s in ROMANTIC_STYLES
    for st in ROMANTIC_STYLES:
        p = build_music_prompt(st, rng)
        assert "piano" in p.lower() and "No vocals" in p and "romantic" in p.lower()
    assert "romantic" in build_image_prompt(ROMANTIC_STYLES[0], rng=rng).lower()


def test_fallback_title_mentions_hours():
    m = fallback("mix", ROMANTIC_STYLES[0], 3 * 3600 + 60, random.Random(0))
    assert "3 Hours" in m.title
    m = fallback("mix", ROMANTIC_STYLES[0], 85 * 60, random.Random(0))
    assert "1 Hour 25 Min" in m.title
    assert "#romanticmusic" in full_description(m.description)


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
    rng = random.Random(5)
    bright = ("glockenspiel", "celesta", "bells", "harp", "bright grand")
    for st in ROMANTIC_STYLES:
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
        vid = pipe.create_daily(st.key)
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
