import re
import shutil
import subprocess

from backend.utils import float_seconds_to_mmssms


def detect_lyrics_bounds(*, input_path: str, noise_threshold_db: int) -> tuple[str, str]:
    result = subprocess.run(
        ["ffmpeg", "-i", input_path, "-af", f"silencedetect=noise={noise_threshold_db}dB:d=1", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )

    stderr = result.stderr

    silence_ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", stderr)]
    silence_starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", stderr)]

    if len(silence_starts) == 0 or silence_starts[0] != 0.0:
        silence_starts.insert(0, 0.0)
        silence_ends.insert(0, 0.0)

    full_duration = get_duration(input_path)
    if silence_ends[-1] != full_duration:
        silence_starts.append(full_duration)
        silence_ends.append(full_duration)

    return (
        float_seconds_to_mmssms(silence_ends[0]) if silence_ends else None,
        float_seconds_to_mmssms(silence_starts[-1]) if silence_starts else None,
    )


def get_duration(input_path: str) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        capture_output=True,
        text=True,
    )
    return float(proc.stdout.strip())


def trim(
    *,
    src: str,
    dest: str,
    duration_seconds: float,
    start_seconds: float | None = None,
    fade_seconds: float | None = None,
) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH; cannot trim. Install it or drop --length.")
    cmd = ["ffmpeg", "-y"]
    if start_seconds is not None:
        cmd += ["-ss", str(start_seconds)]
    cmd += ["-i", src, "-t", str(duration_seconds)]
    if fade_seconds:
        cmd += ["-af", f"afade=t=in:d={fade_seconds},afade=t=out:d={fade_seconds}:st={duration_seconds - fade_seconds}"]
    cmd += ["-c:a", "libmp3lame", "-q:a", "2", dest]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {proc.stderr.strip()}")
    return dest


def attach_cover(*, audio_path: str, cover_path: str, dest: str) -> str:
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-i", cover_path,
        "-map", "0:a", "-map", "1:v",
        "-c:a", "aac", "-b:a", "256k",
        "-c:v", "mjpeg",
        "-disposition:v", "attached_pic",
        dest,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg attach_cover failed: {proc.stderr.strip()}")
    return dest
