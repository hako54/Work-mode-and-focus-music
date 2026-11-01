"""FFmpeg ile ses/video işleme."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

LOOP_SECONDS = 20
FPS = 30


class MediaError(RuntimeError):
    pass


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"{' '.join(cmd[:3])}... başarısız:\n{proc.stderr[-1500:]}")


def duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def master_audio(src: Path, out: Path, fade_in: float = 2.0, fade_out: float = 5.0) -> Path:
    """YouTube için -14 LUFS'e normalize et, yumuşak giriş/çıkış ekle."""
    total = duration(src)
    fade_out = min(fade_out, total / 4)
    af = (
        f"afade=t=in:d={fade_in},afade=t=out:st={max(0.0, total - fade_out):.2f}:d={fade_out},"
        "loudnorm=I=-14:TP=-1.5:LRA=11"
    )
    run(["ffmpeg", "-y", "-i", str(src), "-af", af, "-ar", "44100", "-b:a", "192k", str(out)])
    return out


def crossfade_concat(sources: list[Path], out: Path, xfade: float = 6.0) -> list[float]:
    """Parçaları crossfade ile birleştir. Her parçanın başlangıç saniyesini döndürür."""
    if not sources:
        raise MediaError("Birleştirilecek parça yok")
    durs = [duration(p) for p in sources]
    starts, t = [], 0.0
    for d in durs:
        starts.append(round(t, 2))
        t += d - xfade
    if len(sources) == 1:
        run(["ffmpeg", "-y", "-i", str(sources[0]), "-b:a", "192k", str(out)])
        return starts

    cmd = ["ffmpeg", "-y"]
    for p in sources:
        cmd += ["-i", str(p)]
    parts, prev = [], "[0:a]"
    for i in range(1, len(sources)):
        label = f"[a{i}]"
        parts.append(f"{prev}[{i}:a]acrossfade=d={xfade}:c1=tri:c2=tri{label}")
        prev = label
    parts.append(f"{prev}loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]", "-ar", "44100", "-b:a", "192k", str(out)]
    run(cmd)
    return starts


def make_preview(src: Path, out: Path, max_seconds: float | None = None) -> Path:
    """Telegram'a gönderilecek düşük boyutlu önizleme (bot limiti 50 MB)."""
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-ac", "1", "-b:a", "64k", str(out)]
    run(cmd)
    return out


def cut_segment(src: Path, out: Path, start: float, length: float) -> Path:
    af = f"afade=t=in:d=1.5,afade=t=out:st={length - 2.5:.2f}:d=2.5"
    run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(src),
         "-af", af, "-b:a", "192k", str(out)])
    return out


def make_loop(image: Path, out: Path, size: tuple[int, int] = (1920, 1080), seconds: int | None = None) -> Path:
    """Görselden kesintisiz dönen (nefes alan zoom + film grain) kısa bir döngü klibi üret."""
    w, h = size
    seconds = seconds or LOOP_SECONDS
    frames = seconds * FPS
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
        f"zoompan=z='1.04+0.04*sin(2*PI*on/{frames})':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={FPS},"
        "noise=alls=3:allf=t,vignette=PI/5,format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(seconds), "-i", str(image),
         "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "23",
         "-g", str(FPS * 2), "-pix_fmt", "yuv420p", str(out)])
    return out


def mux(loop: Path, audio: Path, out: Path) -> Path:
    """Döngü klibini ses boyunca tekrarla (video yeniden kodlanmaz, uzun videoda da hızlı)."""
    # Not: -stream_loop ile -shortest + "-c:v copy" durmuyor; süreyi açıkça veriyoruz.
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(loop), "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{duration(audio):.3f}", "-movflags", "+faststart", str(out)])
    return out


def fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def fmt_long(seconds: float) -> str:
    """Başlık/küçük resim için okunur süre: '45 Min', '1 Hour 25 Min', '3 Hours'."""
    total_min = int(seconds // 60)
    h, m = divmod(total_min, 60)
    if not h:
        return f"{total_min} Min"
    hours = f"{h} Hour" + ("s" if h > 1 else "")
    return hours if m < 3 else f"{hours} {m} Min"
