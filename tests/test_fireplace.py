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
    assert not bed.name.startswith("fire_audio_")   # videonun kendi sesi (oda gürültüsü) kullanılmaz
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
    assert "by the Fire" in v["title"]
    assert media.duration(Path(v["video_path"])) >= 60
    short = db.children(vid)[0]
    assert Path(short["video_path"]).exists()

    db.set_setting("fireplace", "0")
    pipe.regenerate(vid, "image")
    assert pipe._background(vid) is None


def test_direct_url_for_drive_and_dropbox():
    d = fireplace.direct_url("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view?usp=sharing")
    assert d == "https://drive.usercontent.google.com/download?id=1AbCdEfGhIjKlMnOp&export=download&confirm=t"
    assert "id=1AbCdEfGhIjKlMnOp" in fireplace.direct_url("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOp")
    assert fireplace.direct_url("https://www.dropbox.com/s/x/fire.mov?dl=0").endswith("dl=1")
    assert fireplace.direct_url("https://example.com/fire.mp4") == "https://example.com/fire.mp4"


def test_4k_link_import_is_downscaled_to_1080p(tmp_path, monkeypatch):
    src = tmp_path / "fire4k.mov"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=3840x2160:rate=30:duration=5",
                    "-f", "lavfi", "-i", "anoisesrc=d=5:c=pink:a=0.3", "-shortest", "-pix_fmt", "yuv420p",
                    str(src)], check=True, capture_output=True)

    class Resp:
        headers = {"Content-Type": "video/quicktime", "Content-Disposition": 'attachment; filename="fire4k.mov"'}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, n):
            with open(src, "rb") as fh:
                while chunk := fh.read(n):
                    yield chunk

    monkeypatch.setattr(fireplace.requests, "get", lambda *a, **k: Resp())
    bg = fireplace.import_url("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view")
    assert bg.kind == "video" and bg.path.suffix == ".mp4"
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(bg.path)], capture_output=True, text=True).stdout.strip()
    assert out == "1920,1080"
    assert not fireplace.ambience_bed().name.startswith("fire_audio_")  # videonun sesi altına konmaz


def test_html_link_gives_clear_error(monkeypatch):
    class Resp:
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
    monkeypatch.setattr(fireplace.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(ValueError, match="Bağlantıya sahip olan herkes"):
        fireplace.import_url("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view")


def test_long_video_rotates_backgrounds_with_crossfades(tmp_path, monkeypatch):
    """Uzun videoda 3 şömine videosu sırayla, yumuşak geçişlerle değişir; video yeniden kodlanmaz."""
    for n, color in enumerate(("red", "green", "blue")):
        src = tmp_path / f"fire{n}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:size=640x360:rate=30:duration=7",
                        "-f", "lavfi", "-i", "anoisesrc=d=7:c=pink:a=0.2", "-shortest", "-pix_fmt", "yuv420p",
                        str(src)], check=True, capture_output=True)
        fireplace.save_upload(src, f"fire{n}.mp4")
    assert len(fireplace.backgrounds()) == 3

    db = Database(tmp_path / "rot.db")
    monkeypatch.setattr("app.pipeline.get_provider", lambda: FakeMusic())
    for k, v in {"daily_min_sec": "60", "daily_max_sec": "60", "mix_min_min": "1", "mix_max_min": "1",
                 "bg_rotate_min_min": "10", "bg_rotate_max_min": "15"}.items():
        db.set_setting(k, v)
    pipe = Pipeline(db)
    monkeypatch.setattr(pipe, "ROTATE_UNIT_SEC", 1)  # dakika yerine saniye: 10-15 sn'de bir değişim
    vid = pipe.create_mix(ROMANTIC_STYLES[0].key)
    out = Path(db.video(vid)["video_path"])
    audio_len = media.duration(out.parent / "mix.mp3")
    assert media.duration(out) == pytest.approx(audio_len, abs=1.0)

    # tüm video hatasız çözülebiliyor ve renkler değişiyor (kırmızı -> yeşil -> mavi)
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True, text=True)
    assert dec.stderr.strip() == ""
    colors = set()
    for t in range(1, int(audio_len) - 1, 3):
        px = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                             "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            capture_output=True).stdout
        if len(px) == 3:
            colors.add(max(range(3), key=lambda c: px[c]))
    assert len(colors) >= 2
    assert not (out.parent / "rotation").exists()  # geçici geçiş dosyaları temizlendi


def test_own_fireplace_videos_can_be_slowed_and_previewed(tmp_path, monkeypatch):
    from app.bot import validate_setting
    src = fire_video(tmp_path / "myfire.mp4", 12)
    bg = fireplace.save_upload(src, "myfire.mp4")
    monkeypatch.setattr(fireplace, "BG_SLOW", 1.0)
    normal = fireplace.loop_for(bg, (640, 360))
    monkeypatch.setattr(fireplace, "BG_SLOW", 1.5)
    slow = fireplace.loop_for(bg, (640, 360))
    assert slow != normal                                    # ayrı önbellek
    assert media.duration(slow) > media.duration(normal) + 3  # 1.5x yavaş: daha uzun döngü
    prev = fireplace.preview_of(bg)
    assert prev.exists() and media.duration(prev) <= 20.5
    assert validate_setting("bg_slow", "1.25") is None and validate_setting("bg_slow", "3")


def test_ratings_steer_background_usage(tmp_path):
    import random
    names = []
    for n in range(3):
        bg = fireplace.save_upload(fire_video(tmp_path / f"r{n}.mp4", 5, audio=False), f"r{n}.mp4")
        names.append(bg.name)
    db = Database(tmp_path / "rate.db")
    pipe = Pipeline(db)
    pipe.set_bg_rating(names[0], 5)   # favori
    pipe.set_bg_rating(names[1], 3)
    pipe.set_bg_rating(names[2], 0)   # 🚫 kullanma
    ratings = pipe.bg_ratings()
    assert ratings == {names[0]: 5, names[1]: 3, names[2]: 0}

    rng = random.Random(4)
    picks = [fireplace.pick_background(rng, ratings=ratings).name for _ in range(600)]
    assert picks.count(names[2]) == 0                       # hiç kullanılmaz
    assert picks.count(names[0]) > 3 * picks.count(names[1])  # 5⭐ ≈ 4x daha sık

    first = fireplace.find_by_id(fireplace.bg_id(fireplace.backgrounds()[0]))
    assert first is not None
    fav = next(b for b in fireplace.backgrounds() if b.name == names[0])
    order = pipe._rotation_order(fav, random.Random(1))
    assert names[2] not in [b.name for b in order]           # uzun videoda da yok
    assert order[0].name == names[0]


def _noise(path, seconds=20):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=d={seconds}:c=brown:a=0.3", str(path)],
                   check=True, capture_output=True)
    return path


def test_real_fire_sound_from_commons_only_free_license(tmp_path, monkeypatch):
    import dataclasses
    fireplace.reset_fire_sound()
    src = _noise(tmp_path / "Fireplace.ogg")
    api = {"query": {"pages": {
        "1": {"index": 1, "title": "File:Copyrighted fire.ogg",
              "imageinfo": [{"url": "https://x/copy.ogg", "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
        "2": {"index": 2, "title": "File:Fireplace.ogg",
              "imageinfo": [{"url": "https://x/Fireplace.ogg", "extmetadata": {"LicenseShortName": {"value": "CC0"}}}]},
    }}}
    got_urls = []

    class Resp:
        def __init__(self, url): self.url = url
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def json(self): return api
        def iter_content(self, n):
            got_urls.append(self.url)
            yield src.read_bytes()

    monkeypatch.setattr(fireplace.requests, "get", lambda url, **k: Resp(url))
    monkeypatch.setattr(fireplace, "CONFIG", dataclasses.replace(fireplace.CONFIG, dry_run=False))
    try:
        bed = fireplace.ambience_bed()
        assert bed.name == "fire_real.m4a" and media.duration(bed) > 10
        assert got_urls == ["https://x/Fireplace.ogg"]          # yalnızca CC0 / kamu malı
        assert "Fireplace.ogg" in fireplace.fire_sound_source()
        assert fireplace.ambience_bed() == bed                  # önbellekten
    finally:
        fireplace.reset_fire_sound()


def test_uploaded_fire_sound_wins_and_resets(tmp_path):
    fireplace.reset_fire_sound()
    with pytest.raises(media.MediaError):
        fireplace.save_fire_sound(_noise(tmp_path / "short.wav", 5))     # çok kısa
    out = fireplace.save_fire_sound(_noise(tmp_path / "mine.mp3"))
    assert fireplace.ambience_bed() == out and "yüklediğin" in fireplace.fire_sound_source()
    fireplace.reset_fire_sound()
    assert fireplace.ambience_bed() != out
