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

    return (
        float_seconds_to_mmssms(silence_ends[0]) if silence_ends else None,
        float_seconds_to_mmssms(silence_starts[-1]) if silence_starts else None,
    )


def trim(src: str, dest: str, seconds: float) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH; cannot trim. Install it or drop --length.")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-t",
        str(seconds),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        dest,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed: {proc.stderr.strip()}")
    return dest
