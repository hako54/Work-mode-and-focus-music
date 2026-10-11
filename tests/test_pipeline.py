import random
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import media, visuals
from app.bot import validate_setting
from app.config import CONFIG
from app.db import Database, iso
from app.metadata import fallback, full_description
from app.pipeline import Pipeline, order_for_flow
from app.styles import STYLE_BY_KEY, STYLES, build_music_prompt, pick_style


def sine(path: Path, seconds: float, freq: int = 440) -> Path:
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
                    "-b:a", "128k", str(path)], check=True, capture_output=True)
    return path


class FakeMusic:
    def compose(self, prompt, duration_sec, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return sine(out_path, min(duration_sec, 20), random.randint(200, 600))


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "t.db")


@pytest.fixture
def pipe(db, monkeypatch):
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    monkeypatch.setattr("app.media.LOOP_SECONDS", 2)
    db.set_setting("daily_min_sec", "60")
    db.set_setting("daily_max_sec", "60")
    return Pipeline(db)


def test_pick_style_avoids_recent_and_respects_disabled():
    rng = random.Random(1)
    for _ in range(50):
        s = pick_style(["lofi_hiphop", "ambient_piano"], {}, rng, disabled={"rain_lofi"})
        assert s.key not in {"lofi_hiphop", "ambient_piano", "rain_lofi"}


def test_music_prompt_is_instrumental():
    p = build_music_prompt(STYLES[0], random.Random(0))
    assert "No vocals" in p and "BPM" in p


def test_order_for_flow_starts_with_best_and_keeps_all():
    tracks = [{"id": i, "style_key": s.key, "score": float(i)} for i, s in enumerate(STYLES)]
    ordered = order_for_flow(tracks)
    assert ordered[0]["id"] == len(STYLES) - 1
    assert sorted(t["id"] for t in ordered) == sorted(t["id"] for t in tracks)


def test_fmt_ts():
    assert media.fmt_ts(0) == "00:00"
    assert media.fmt_ts(3725) == "1:02:05"


def test_validate_setting():
    assert validate_setting("publish_time", "17:30") is None
    assert validate_setting("publish_time", "25:00")
    assert validate_setting("short_seconds", "90")
    assert validate_setting("make_shorts", "1") is None


def test_fallback_meta_and_description():
    m = fallback("compilation", STYLES[0], 3600, random.Random(0))
    assert "60" in m.title
    d = full_description(m.description, "00:00 A\n03:10 B")
    assert "Tracklist" in d and len(d) < 5000


def test_next_publish_at(db):
    p = Pipeline(db)
    db.set_setting("publish_time", "17:00")
    morning = datetime(2026, 1, 5, 6, 0, tzinfo=timezone.utc)   # İstanbul 09:00
    evening = datetime(2026, 1, 5, 16, 0, tzinfo=timezone.utc)  # İstanbul 19:00
    assert p.next_publish_at(morning) == datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)
    assert p.next_publish_at(evening) is None


def test_thumbnail_and_vertical(tmp_path):
    img = visuals.procedural_image(tmp_path / "a.png", (640, 360), seed=3)
    thumb = visuals.make_thumbnail(img, tmp_path / "t.jpg", "DEEP FOCUS", "60 MIN MIX")
    vert = visuals.vertical_from(img, tmp_path / "v.png")
    from PIL import Image
    assert Image.open(thumb).size == (1280, 720)
    assert Image.open(vert).size == (1080, 1920)


def test_daily_end_to_end_and_dry_run_approve(pipe, db):
    vid = pipe.create_daily("chillhop_jazz")
    v = db.video(vid)
    assert v["status"] == "pending" and v["title"]
    assert Path(v["video_path"]).exists() and Path(v["thumb_path"]).exists()
    assert media.duration(Path(v["video_path"])) == pytest.approx(20, abs=1.5)
    shorts = db.children(vid)
    assert len(shorts) == 1 and shorts[0]["status"] == "pending"

    ids = pipe.approve(vid)
    assert len(ids) == 2
    assert db.video(vid)["status"] in ("scheduled", "published")
    assert db.children(vid)[0]["status"] == "scheduled"
    assert not Path(v["video_path"]).exists()  # yüklenen mp4 silinir
    assert Path(db.track(v["track_id"])["audio_path"]).exists()  # ses derleme için kalır


def test_compilation_picks_top_tracks_and_fills_gap(pipe, db):
    for i in range(3):
        vid = pipe.create_daily(STYLES[i].key)
        pipe.approve(vid)
        db.update_video(vid, views=100 * (i + 1), status="published",
                        publish_at=iso(datetime.now(timezone.utc) - timedelta(days=3)))
    db.set_setting("compilation_min_min", "1")   # 3 x ~14 sn yetmez -> ek parça üretilmeli
    db.set_setting("compilation_max_min", "10")
    chosen = pipe.select_compilation_tracks()
    assert chosen[0]["score"] == max(c["score"] for c in chosen)

    cid = pipe.create_compilation()
    c = db.video(cid)
    assert c["status"] == "pending"
    assert "Tracklist" in c["description"] and "00:00" in c["description"]
    rows = db.query("SELECT * FROM compilation_tracks WHERE video_id = ?", (cid,))
    assert len(rows) >= 4  # 3 yayınlanmış + en az 1 exclusive
    assert media.duration(Path(c["video_path"])) >= 60


def test_compilation_due(pipe, db):
    assert not pipe.compilation_due()
    vid = pipe.create_daily()
    pipe.approve(vid)
    old = iso(datetime.now(timezone.utc) - timedelta(days=16))
    db.update_video(vid, created_at=old)
    assert pipe.compilation_due()
