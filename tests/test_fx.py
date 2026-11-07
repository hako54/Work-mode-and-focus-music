"""Sinematik işleme, kendi videoların önceliği, yapay zeka sahnesi ve insanlı sahne sırası."""
import dataclasses
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app import fireplace, fx, media, profiles, visuals
from app.bot import validate_setting
from app.db import Database
from app.pipeline import Pipeline
from app.themes import THEME_BY_KEY
from tests.test_pipeline import FakeMusic


@pytest.fixture(autouse=True)
def romantic():
    profiles.set_active("romantic")
    yield
    profiles.set_active(None)


@pytest.fixture
def pipe(tmp_path, monkeypatch):
    db = Database(tmp_path / "fx.db")
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    monkeypatch.setattr("app.media.LOOP_SECONDS", 2)
    monkeypatch.setattr(fx, "IMAGE_LOOP_SEC", 2.0)
    db.set_setting("daily_min_sec", "60")
    db.set_setting("daily_max_sec", "60")
    return Pipeline(db)


def _image(path: Path, size=(960, 540)) -> Path:
    a = np.zeros((size[1], size[0], 3), np.uint8)
    a[..., 0] = np.linspace(40, 200, size[0])[None, :]
    a[..., 1] = 60
    Image.fromarray(a).save(path)
    return path


@pytest.mark.parametrize("kind", ["embers", "snow", "dust"])
def test_particles_loop_seamlessly(kind):
    for length in (12.0, 47.3):
        p = fx._Particles(kind, length, seed=3)
        first, last = p.frame(0.0), p.frame(length)
        assert np.array_equal(first, last)          # döngü sonunda parçacıklar atlamaz
        assert p.frame(length / 3).max() > 0         # görünür parçacık var


def test_particles_by_theme():
    assert fx.particles_for("fireplace") == "embers"
    assert fx.particles_for("winter") == "snow"
    assert fx.particles_for("lake") == "dust"
    assert fx.particles_for("rain") is None


def test_cinematic_from_image_and_video(tmp_path):
    img = _image(tmp_path / "a.png")
    out = fx.cinematic(img, tmp_path / "a.mp4", (640, 360), theme_key="fireplace", length=2.0)
    assert abs(media.duration(out) - 2.0) < 0.2
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=3",
                    "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    out2 = fx.cinematic(src, tmp_path / "v_fx.mp4", (360, 640), theme_key="rain")   # parçacıksız yol
    assert abs(media.duration(out2) - 3.0) < 0.2
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(out2)], capture_output=True, text=True)
    assert probe.stdout.strip() == "360,640"
    assert not list(tmp_path.glob("*.part.mp4"))


def test_scene_plan_order(pipe, monkeypatch):
    import app.pipeline as pl
    fire, lake = THEME_BY_KEY["fireplace"], THEME_BY_KEY["lake"]
    assert pipe._scene_plan(fire, "scene") == ["people", "stock"]          # kendi videon yok
    monkeypatch.setattr(pipe, "_own_videos", lambda theme=None: [object()])
    assert pipe._scene_plan(fire, "scene")[0] == "own"
    assert pipe._scene_plan(lake, "scene")[0] == "people"                   # göl kendi-video teması değil
    monkeypatch.setattr(pl, "CONFIG", dataclasses.replace(pl.CONFIG, stability_api_key="x"))
    pipe.db.set_setting("scene_counter", "1")
    assert pipe._scene_plan(lake, "scene") == ["people", "stock"]          # varsayılan: yapay zeka görseli yok
    pipe.db.set_setting("ai_scene_every", "2")                              # istenirse her 2. sahne
    assert pipe._scene_plan(lake, "scene")[:2] == ["ai", "people"]
    pipe.db.set_setting("scene_counter", "2")
    assert pipe._scene_plan(lake, "scene") == ["people", "stock"]
    pipe.db.set_setting("scene_people", "0")
    assert pipe._scene_plan(lake, "people") == ["people", "stock"]
    assert pipe._scene_plan(lake, "scene") == ["stock"]


def test_own_rated_video_is_used_with_crackle(pipe, monkeypatch):
    src = fireplace.user_dir() / "my_fire_test.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=6",
                    "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    try:
        calls = []
        monkeypatch.setattr(fx, "cinematic", lambda s, o, size, **k: calls.append(k["theme_key"]) or
                            Path(o).write_bytes(Path(s).read_bytes()) or o)
        pipe.db.set_setting("cinematic", "1")
        assert pipe._own_videos(THEME_BY_KEY["fireplace"]) and not pipe._own_videos(THEME_BY_KEY["autumn"])
        pipe.set_bg_rating(src.name, 5)
        vid = pipe.create_daily(series_key="romance", theme_key="fireplace")
        d = Path(pipe.db.video(vid)["video_path"]).parent
        assert (d / "visual.txt").read_text() == "own"
        assert pipe._background(vid).name == src.name          # çıtırtı sesi eklenir
        assert pipe._collage(vid) and calls and set(calls) == {"fireplace"}
        assert pipe.db.get_setting("last_own_video") == src.name
    finally:
        src.unlink(missing_ok=True)


def test_ai_scene_with_stability(pipe, monkeypatch, tmp_path):
    import app.pipeline as pl
    monkeypatch.setattr(pl, "CONFIG", dataclasses.replace(pl.CONFIG, stability_api_key="x"))
    prompts = []

    def fake_gen(prompt, out, aspect="16:9", seed=None, fallback=True):
        prompts.append(prompt)
        return _image(out, (960, 540))
    monkeypatch.setattr(visuals, "generate_image", fake_gen)
    vid = pipe.create_daily(series_key="romance", theme_key="lake", visual="ai")
    d = Path(pipe.db.video(vid)["video_path"]).parent
    assert (d / "visual.txt").read_text() == "ai"
    assert pipe._collage(vid) and pipe._collage(vid, "v")
    assert "couple" in prompts[0] and "no text" in prompts[0]


def test_ai_without_key_falls_back(pipe):
    vid = pipe.create_daily(series_key="romance", theme_key="lake", visual="ai")   # anahtar/Pexels yok
    assert pipe._background(vid) is not None                                     # şömineye düşer


def test_scene_never_uses_a_photo(pipe, monkeypatch, tmp_path):
    from app import stock
    monkeypatch.setattr(stock, "available", lambda: True)
    monkeypatch.setattr(stock, "fetch_scene_clips", lambda *a, **k: [])
    monkeypatch.setattr(stock, "fetch_scene", lambda *a, **k: stock.StockItem("p1", "photo", _image(tmp_path / "p.png")))
    vid = pipe.create_daily(series_key="romance", theme_key="lake")
    d = Path(pipe.db.video(vid)["video_path"]).parent
    assert not (d / "visual.txt").exists() and pipe._background(vid) is not None   # fotoğraf yerine şömine videosu


def test_no_camera_movement():
    assert "sin(" not in fx._fit((1920, 1080))


def test_new_settings_validate():
    assert validate_setting("cinematic", "0") is None and validate_setting("cinematic", "2")
    assert validate_setting("own_video_themes", "fireplace,winter") is None
    assert "bilinmeyen" in validate_setting("own_video_themes", "fireplace,uzay")
    assert validate_setting("own_video_min_rating", "5") is None and validate_setting("own_video_min_rating", "7")
    assert validate_setting("ai_scene_every", "3") is None
