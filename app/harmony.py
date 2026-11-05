"""Parçalar arası armonik uyum: biten notalar ile başlayan notalar çatışmasın.

Her parçanın son ~12 saniyesi ve ilk ~12 saniyesi için 12 perdelik bir "kromagram" (hangi notaların
ne kadar çaldığı) çıkarılır. Uyum, bitiş profiliyle başlangıç profilinin benzerliğidir (aynı/yakın
notalar = yüksek). Derlemede parçalar bu uyuma göre sıralanır; uyum düşükse geçiş kısaltılır ki iki
farklı ton uzun süre üst üste binmesin. Müzik üretilirken de parçaların tonik akorla başlayıp tonik
akorla bitmesi istenir (bkz. TONIC_HINT).
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import media

SR = 11025
EDGE_SEC = 12.0
TONIC_HINT = ("Begin softly on the home (tonic) chord and end by resolving gently back onto the tonic chord, "
              "letting a warm consonant chord ring out at the very end, so the piece starts and ends at rest.")


def _decode(path: Path, start: float, dur: float) -> np.ndarray:
    proc = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.2f}", "-t", f"{dur:.2f}",
                           "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                          capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype="<f4").astype(np.float64)


def chroma(samples: np.ndarray) -> np.ndarray:
    """12 perdelik enerji profili (C, C#, … B), birim uzunluğa normalize."""
    if samples.size < 2048:
        return np.zeros(12)
    n = 4096
    hop = 2048
    win = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    band = (freqs >= 55) & (freqs <= 2000)
    midi = 69 + 12 * np.log2(freqs[band] / 440.0)
    pcs = np.mod(np.round(midi), 12).astype(int)
    prof = np.zeros(12)
    for i in range(0, samples.size - n, hop):
        spec = np.abs(np.fft.rfft(samples[i:i + n] * win))[band] ** 2
        np.add.at(prof, pcs, spec)
    norm = np.linalg.norm(prof)
    return prof / norm if norm > 0 else prof


@lru_cache(maxsize=512)
def _edges_cached(path: str, mtime: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    p = Path(path)
    total = media.duration(p)
    edge = min(EDGE_SEC, total / 3)
    head = chroma(_decode(p, 1.0, edge))                    # ilk saniye: fade-in sessizliği atlanır
    tail = chroma(_decode(p, total - edge - 1.0, edge))     # son saniye: fade-out sessizliği atlanır
    return tuple(head), tuple(tail)


def edges(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(başlangıç profili, bitiş profili)"""
    h, t = _edges_cached(str(path), path.stat().st_mtime)
    return np.array(h), np.array(t)


def fit(prev_tail: np.ndarray, next_head: np.ndarray) -> float:
    """0..1: önceki parçanın bitiş notaları ile sonrakinin başlangıç notaları ne kadar uyumlu."""
    if not prev_tail.any() or not next_head.any():
        return 0.5
    return float(np.clip(np.dot(prev_tail, next_head), 0.0, 1.0))


def xfade_for(score: float, base: float) -> float:
    """Uyum yüksekse uzun bindirme; düşükse kısa (iki farklı ton uzun süre çatışmasın)."""
    if score >= 0.75:      # aynı / çok yakın tonlar: uzun, iç içe geçiş
        return base
    if score >= 0.5:       # paralel minör-majör gibi: biraz kısa
        return max(4.0, base * 0.7)
    if score >= 0.25:      # komşu tonlar (ör. C -> G): orta
        return max(4.0, base * 0.45)
    return max(3.0, base * 0.25)  # çatışan tonlar: en kısa, üst üste binme yok denecek kadar


def order(tracks: list[dict], first: dict | None = None) -> list[dict]:
    """Her adımda, bitiş notalarına en uyumlu başlangıcı olan parçayı seç (açgözlü zincir).

    tracks: {"audio_path": ..., "score": ...}; first verilmezse en popüler (score) parçayla başlar."""
    if len(tracks) <= 2:
        return list(tracks)
    prof = {id(t): edges(Path(t["audio_path"])) for t in tracks}
    remaining = list(tracks)
    cur = first if first in remaining else max(remaining, key=lambda t: t.get("score", 0.0))
    remaining.remove(cur)
    out = [cur]
    while remaining:
        tail = prof[id(cur)][1]
        cur = max(remaining, key=lambda t: (fit(tail, prof[id(t)][0]), t.get("score", 0.0)))
        remaining.remove(cur)
        out.append(cur)
    return out


def transitions(paths: list[Path], base: float) -> list[float]:
    """Ardışık her parça çifti için geçiş süresi."""
    prof = [edges(p) for p in paths]
    return [xfade_for(fit(prof[i][1], prof[i + 1][0]), base) for i in range(len(paths) - 1)]
