"""Şömine modu: arka plan döngüleri, çıtırtı sesi, Telegram yüklemesi ve mixe entegrasyon."""
import subprocess
from pathlib import Path

import pytest

from app import fireplace, media, profiles
from app.db import Database
from app.pipeline import Pipeline
from app.styles import ROMANTIC_STYLES
from tests.test_pipeline import FakeMusic


@pytest.fixture(autouse=True)
def fast(monkeypatch, tmp_path):
    profiles.set_active("romantic")
    monkeypatch.setattr(fireplace, "FIRE_LOOP_SECONDS", 1)
    monkeypatch.setattr(fireplace, "CRACKLE_SECONDS", 8)
    monkeypatch.setattr(fireplace, "user_dir", lambda: _mk(tmp_path / "user"))
    monkeypatch.setattr(fireplace, "cache_dir", lambda: _mk(tmp_path / "cache"))
    monkeypatch.setattr("app.media.LOOP_SECONDS", 2)
    yield
    profiles.set_active(None)


def _mk(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def fire_video(path: Path, seconds: int = 6, audio: bool = True) -> Path:
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"anoisesrc=d={seconds}:c=pink:a=0.3"]
    cmd += ["-shortest", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def test_bundled_photo_is_default_background():
    bgs = fireplace.backgrounds()
    assert bgs and all(b.kind == "image" for b in bgs)
    assert any(b.path.parent == fireplace.BUNDLED_DIR for b in bgs)


def test_animated_photo_loop_is_cached():
    bg = fireplace.backgrounds()[0]
    loop = fireplace.loop_for(bg, (640, 360))
    assert media.duration(loop) == pytest.approx(1, abs=0.2)
    assert fireplace.loop_for(bg, (640, 360)) == loop  # ikinci çağrı önbellekten


def test_synth_crackle_is_loopable_audio(tmp_path):
    out = fireplace.synth_crackle(tmp_path / "c.m4a")
    assert media.duration(out) == pytest.approx(8, abs=0.3)
    assert fireplace._mean_volume(out) > -40


def test_seamless_video_loop(tmp_path):
    src = fire_video(tmp_path / "f.mp4", 6)
    out = fireplace.seamless_video_loop(src, tmp_path / "loop.mp4", (320, 180), xfade=1.0)
    assert media.duration(out) == pytest.approx(5, abs=0.2)


def test_uploaded_video_replaces_photos_and_provides_fire_sound(tmp_path):
    src = fire_video(tmp_path / "phone.mov", 6)
    bg = fireplace.save_upload(src, "my fire.mov")
    assert bg.kind == "video" and bg.path.exists()
    assert [b.kind for b in fireplace.backgrounds()] == ["video"]
    bed = fireplace.ambience_bed()
    assert bed.name.startswith("fire_audio_")
    assert fireplace.remove(bg.name) and not fireplace.backgrounds()[0].kind == "video"


def test_rejects_unknown_upload(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    with pytest.raises(ValueError):
        fireplace.save_upload(f, "x.txt")


def test_mix_with_fireplace_and_crackle(tmp_path, monkeypatch):
    db = Database(tmp_path / "f.db")
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    for k, v in {"daily_min_sec": "60", "daily_max_sec": "60", "mix_min_min": "1", "mix_max_min": "1"}.items():
        db.set_setting(k, v)
    pipe = Pipeline(db)
    vid = pipe.create_mix(ROMANTIC_STYLES[0].key)
    v = db.video(vid)
    assert pipe._background(vid) is not None
    assert "Fireplace" in v["title"] or "fireplace" in v["title"].lower()
    assert media.duration(Path(v["video_path"])) >= 60
    short = db.children(vid)[0]
    assert Path(short["video_path"]).exists()

    db.set_setting("fireplace", "0")
    pipe.regenerate(vid, "image")
    assert pipe._background(vid) is None
