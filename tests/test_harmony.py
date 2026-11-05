"""Parçalar arası armonik uyum: biten notalarla başlayan notalar uyumlu olsun."""
import subprocess
from pathlib import Path

import pytest

from app import harmony, media


def tone(path: Path, freqs: list[float], seconds: float = 30) -> Path:
    """Verilen frekansların akoru (ör. C majör: C-E-G)."""
    inputs = []
    for f in freqs:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={seconds}"]
    mix = "".join(f"[{i}:a]" for i in range(len(freqs))) + f"amix=inputs={len(freqs)}"
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", mix, "-b:a", "128k", str(path)],
                   check=True, capture_output=True)
    return path


C_MAJ = [261.63, 329.63, 392.00]
A_MIN = [220.00, 261.63, 329.63]          # C majörle iki ortak nota (C, E): uyumlu
FS_MAJ = [369.99, 466.16, 277.18]         # F# majör: C majörle ortak nota yok, çatışır


def test_fit_matches_shared_notes(tmp_path):
    c = tone(tmp_path / "c.mp3", C_MAJ)
    a = tone(tmp_path / "a.mp3", A_MIN)
    fs = tone(tmp_path / "fs.mp3", FS_MAJ)
    c_tail = harmony.edges(c)[1]
    same = harmony.fit(c_tail, harmony.edges(tone(tmp_path / "c2.mp3", C_MAJ))[0])
    near = harmony.fit(c_tail, harmony.edges(a)[0])
    clash = harmony.fit(c_tail, harmony.edges(fs)[0])
    assert same > near > clash
    assert same > 0.9 and clash < 0.3
    assert harmony.xfade_for(same, 12) == 12 and harmony.xfade_for(clash, 12) < 5


def test_order_puts_compatible_track_next_and_shortens_clashing_fades(tmp_path):
    c = {"audio_path": str(tone(tmp_path / "c.mp3", C_MAJ)), "score": 10.0, "n": "C"}
    fs = {"audio_path": str(tone(tmp_path / "fs.mp3", FS_MAJ)), "score": 5.0, "n": "F#"}
    a = {"audio_path": str(tone(tmp_path / "a.mp3", A_MIN)), "score": 1.0, "n": "Am"}
    ordered = harmony.order([c, fs, a])
    assert [t["n"] for t in ordered] == ["C", "Am", "F#"]      # C'den sonra uyumlu Am, F# en sona
    fades = harmony.transitions([Path(t["audio_path"]) for t in ordered], 12.0)
    assert fades[0] > fades[1]                                # Am->F# çatışıyor: kısa geçiş

    out = tmp_path / "mix.mp3"
    starts = media.crossfade_concat([Path(t["audio_path"]) for t in ordered], out, xfade=fades)
    assert starts[1] == pytest.approx(30 - fades[0], abs=0.2)
    assert media.duration(out) == pytest.approx(90 - sum(fades), abs=0.6)
