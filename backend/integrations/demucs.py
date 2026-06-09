import glob
import os
import shutil
import subprocess
import tempfile


def separate_vocals(input_path: str, output_dir: str | None = None) -> str:
    tmpdir = tempfile.mkdtemp()

    subprocess.run(
        ["demucs-infer", "-d", "cpu", "-o", tmpdir, input_path],
        check=True,
        capture_output=True,
    )

    base = os.path.splitext(os.path.basename(input_path))[0]
    vocals_path = os.path.join(tmpdir, "*", base, "vocals.wav")
    matches = glob.glob(vocals_path)
    if not matches:
        raise FileNotFoundError(f"vocals.wav not found at {vocals_path}")

    if output_dir:
        dest = os.path.join(output_dir, "vocals.wav")
        shutil.copy2(matches[0], dest)
        return dest

    return matches[0]
