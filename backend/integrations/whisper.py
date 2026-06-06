import os
import re
import subprocess
import tempfile

from backend.utils import srt_timestamp_to_mmssms

def _parse_srt(srt_text: str) -> list[dict]:
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.+?)(?=\n\n|\n*$)",
        re.DOTALL,
    )
    result = []
    for start, end, text in pattern.findall(srt_text):
        start_fmt = srt_timestamp_to_mmssms(start)
        end_fmt = srt_timestamp_to_mmssms(end)
        lyric = text.strip().replace("\n", " ")
        result.append({(start_fmt, end_fmt): lyric})
    return result


def transcribe(song_path: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                "whisper",
                song_path,
                "--model",
                "large",
                "--language",
                "en",
                "--output_format",
                "srt",
                "--output_dir",
                tmpdir,
            ],
            check=True,
            capture_output=True,
        )

        base = os.path.splitext(os.path.basename(song_path))[0]
        srt_path = os.path.join(tmpdir, f"{base}.srt")

        with open(srt_path) as f:
            srt_text = f.read()

    return _parse_srt(srt_text)
