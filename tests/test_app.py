"""HTTP contract tests for locally persisted song artifacts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.app as app_module
from backend.integrations.music_types import Clip


class SongArtifactRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_output_dir = app_module.OUTPUT_DIR
        app_module.OUTPUT_DIR = self.temp_dir.name
        self.client = app_module.app.test_client()

        self.song_dir = Path(self.temp_dir.name) / "song-123"
        self.song_dir.mkdir()
        (self.song_dir / "source.mp3").write_bytes(b"original-source-audio")
        (self.song_dir / "response.json").write_text(
            json.dumps(
                {
                    "source": {
                        "provider": "suno",
                        "clip_id": "clip-123",
                        "file_name": "source.mp3",
                    }
                }
            )
        )

    def tearDown(self):
        app_module.OUTPUT_DIR = self.previous_output_dir
        self.temp_dir.cleanup()

    def test_serves_the_persisted_original_source_audio(self):
        response = self.client.get("/songs/song-123/source")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertEqual(response.data, b"original-source-audio")
        response.close()

    def test_redirects_to_a_fresh_provider_playback_url(self):
        if not hasattr(app_module, "mint_playback_url"):
            self.fail("The app must delegate source playback to the provider registry")

        with patch.object(app_module, "mint_playback_url") as mint:
            mint.return_value = (
                "https://api.suno.com/v0/audio/clip-123/stream?t=fresh-token"
            )

            response = self.client.get("/songs/song-123/source/playback")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://api.suno.com/v0/audio/clip-123/stream?t=fresh-token",
        )
        mint.assert_called_once_with("suno", "clip-123")

    def test_generation_persists_provider_source_metadata_without_a_token(self):
        clip = Clip(
            id="clip-123",
            status="complete",
            audio_url="",
            path="/tmp/source.mp3",
        )
        with (
            patch.object(app_module, "generate_clip", return_value=clip),
            patch.object(app_module, "generate_album_art", return_value="/tmp/cover.png"),
            patch.object(app_module, "_postprocess_song"),
            patch.object(app_module.Image, "open") as image_open,
            patch.object(app_module, "attach_cover"),
        ):
            image_open.return_value.convert.return_value.save.return_value = None
            response = app_module._produce_song(
                prompt_result={"lyrics": "lyrics", "style_prompt": "style"},
                input_message="message",
                song_id="song-123",
                music_model="suno",
            )

        self.assertIn("source", response)
        self.assertEqual(
            response["source"],
            {
                "provider": "suno",
                "clip_id": "clip-123",
                "file_name": "source.mp3",
                "local_url": "/songs/song-123/source",
                "playback_url": "/songs/song-123/source/playback",
            },
        )
        persisted = json.loads((self.song_dir / "response.json").read_text())
        self.assertEqual(persisted["source"], response["source"])

    def test_local_web_client_exposes_provider_source_controls(self):
        client_source = (Path(app_module.STATIC_DIR) / "index.html").read_text()

        self.assertIn('id="source-audio"', client_source)
        self.assertIn('id="source-player"', client_source)
        self.assertIn('id="source-playback-link"', client_source)
        self.assertIn("data.source.local_url", client_source)
        self.assertIn("data.source.playback_url", client_source)


if __name__ == "__main__":
    unittest.main()
