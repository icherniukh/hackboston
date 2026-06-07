import glob
import os
import shutil
import subprocess
import tempfile


def separate_vocals(input_path: str, output_dir: str | None = None) -> str:
    # soundfile (used by demucs-mlx) can't handle many MP3 files,
    # so pre-convert to WAV with ffmpeg which handles all codecs.
    should_convert = input_path.lower().endswith(".mp3")
    if should_convert:
        wav_path = input_path.rsplit(".", 1)[0] + "_convert.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-c:a", "pcm_f32le", "-ar", "44100", wav_path],
            check=True, capture_output=True,
        )
        input_path = wav_path

    tmpdir = tempfile.mkdtemp()

    subprocess.run(
        [os.path.expanduser("~/.local/bin/demucs-mlx"), "-o", tmpdir, input_path],
        check=True,
        capture_output=True,
    )

    base = os.path.splitext(os.path.basename(input_path))[0]
    vocals_path = os.path.join(tmpdir, base, "vocals.wav")
    matches = glob.glob(vocals_path)
    if not matches:
        raise FileNotFoundError(f"vocals.wav not found at {vocals_path}")

    if output_dir:
        dest = os.path.join(output_dir, "vocals.wav")
        shutil.copy2(matches[0], dest)
        return dest

    return matches[0]
