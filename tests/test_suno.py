"""Contract tests for the Suno client."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from backend.integrations.suno import SunoClient, _build_parser


class _Response:
    status_code = 200
    text = ""
    reason = "OK"

    def __init__(self, body: dict | None = None):
        self.body = body or {}

    def json(self):
        return self.body

    def iter_content(self, chunk_size: int):
        yield b"source-audio"


class _Session:
    def __init__(self):
        self.headers = {}
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.get_calls.append((url, kwargs))
        return _Response()

    def post(self, url: str, **kwargs):
        self.post_calls.append((url, kwargs))
        return _Response({"url": "https://api.suno.com/v0/audio/clip-123/stream?t=token"})


class SunoClientDownloadTests(unittest.TestCase):
    def test_cli_rejects_the_unsupported_length_option(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            _build_parser().parse_args(["--length", "30"])

    def test_download_uses_the_authenticated_stream_endpoint(self):
        client = SunoClient(base_url="https://api.suno.com", timeout=12)
        session = _Session()
        client.session = session

        with tempfile.TemporaryDirectory() as tmp_dir:
            destination = Path(tmp_dir) / "suno.mp3"
            client.download("clip-123", str(destination))

            self.assertEqual(destination.read_bytes(), b"source-audio")

        self.assertEqual(
            session.get_calls,
            [
                (
                    "https://api.suno.com/v0/audio/clip-123/stream",
                    {"timeout": 12, "stream": True},
                )
            ],
        )

    def test_mint_playback_url_uses_the_clip_scoped_token_endpoint(self):
        client = SunoClient(base_url="https://api.suno.com", timeout=12)
        session = _Session()
        client.session = session

        if not hasattr(client, "mint_playback_url"):
            self.fail("SunoClient must mint a clip-scoped playback URL")

        url = client.mint_playback_url("clip-123")

        self.assertEqual(
            url, "https://api.suno.com/v0/audio/clip-123/stream?t=token"
        )
        self.assertEqual(
            session.post_calls,
            [
                (
                    "https://api.suno.com/v0/audio/clip-123/playback-token",
                    {"timeout": 12},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
