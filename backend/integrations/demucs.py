import glob
import os
import subprocess
import tempfile


def separate_vocals(input_path: str) -> str:
    tmpdir = tempfile.mkdtemp()

    subprocess.run(
        ["demucs", "-d", "cpu", "-o", tmpdir, input_path],
        check=True,
        capture_output=True,
    )

    base = os.path.splitext(os.path.basename(input_path))[0]
    vocals_path = os.path.join(tmpdir, "*", base, "vocals.wav")
    matches = glob.glob(vocals_path)
    if not matches:
        raise FileNotFoundError(f"vocals.wav not found at {vocals_path}")

    return matches[0]
