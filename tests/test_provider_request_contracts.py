"""Request-shape contracts for every music-provider adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.integrations import fal_music, replicate_music
from backend.integrations.suno import SunoClient


class _SunoResponse:
    status_code = 200
    text = ""
    reason = "OK"

    def json(self):
        return {"id": "clip-123"}


class _SunoSession:
    def __init__(self):
        self.headers = {}
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return _SunoResponse()


class SunoRequestContractTests(unittest.TestCase):
    def test_custom_generation_payload_uses_lyrics_and_style_only(self):
        client = SunoClient(base_url="https://api.suno.com", timeout=12)
        session = _SunoSession()
        client.session = session

        self.assertEqual(client.submit(lyrics="lyrics", style="style"), "clip-123")
        self.assertEqual(
            session.calls,
            [
                (
                    "https://api.suno.com/v0/audio",
                    {"json": {"lyrics": "lyrics", "style": "style"}, "timeout": 12},
                )
            ],
        )


class FalRequestContractTests(unittest.TestCase):
    def test_every_fal_adapter_builds_its_documented_request_shape(self):
        cases = [
            (
                "generate_ace_step",
                "fal-ai/ace-step",
                {"tags": "style", "lyrics": "lyrics", "duration": 30},
                True,
            ),
            (
                "generate_ace_step_prompt_to_audio",
                "fal-ai/ace-step/prompt-to-audio",
                {
                    "prompt": (
                        'style The ONLY words to sing, verbatim, in quotes: "lyrics". '
                        "Everything before this sentence is style/production guidance, not lyrics to vocalize."
                    ),
                    "duration": 30,
                    "instrumental": False,
                },
                True,
            ),
            (
                "generate_minimax_v2",
                "fal-ai/minimax-music/v2",
                {"prompt": "style", "lyrics_prompt": "lyrics"},
                False,
            ),
            (
                "generate_minimax_v25",
                "fal-ai/minimax-music/v2.5",
                {"prompt": "style", "is_instrumental": False, "lyrics": "lyrics"},
                False,
            ),
            (
                "generate_minimax_v26",
                "fal-ai/minimax-music/v2.6",
                {"prompt": "style", "is_instrumental": False, "lyrics": "lyrics"},
                False,
            ),
            (
                "generate_lyria3",
                "fal-ai/lyria3",
                {
                    "prompt": (
                        'style The ONLY words to sing, verbatim, in quotes: "lyrics". '
                        "Everything before this sentence is style/production guidance, not lyrics to vocalize."
                    )
                },
                False,
            ),
        ]
        with patch.object(fal_music, "_run", return_value="clip") as run:
            for function_name, model_id, arguments, supports_duration in cases:
                with self.subTest(function_name=function_name):
                    run.reset_mock()
                    call_kwargs = {"out_dir": "/tmp/out", "lyrics": "lyrics", "style": "style"}
                    if supports_duration:
                        call_kwargs["duration"] = 30
                    getattr(fal_music, function_name)(**call_kwargs)
                    self.assertEqual(run.call_args.args[:2], (model_id, arguments))
                    self.assertEqual(run.call_args.kwargs["out_dir"], "/tmp/out")

    def test_elevenlabs_uses_a_30_second_structured_composition_plan(self):
        with patch.object(fal_music, "_run", return_value="clip") as run:
            fal_music.generate_elevenlabs(
                out_dir="/tmp/out", lyrics="line one\nline two", style="style", duration=30
            )

        arguments = run.call_args.args[1]
        self.assertEqual(run.call_args.args[0], "fal-ai/elevenlabs/music")
        self.assertFalse(arguments["force_instrumental"])
        self.assertEqual(arguments["composition_plan"]["sections"][0]["duration_ms"], 30_000)
        self.assertEqual(arguments["composition_plan"]["sections"][0]["lines"], ["line one", "line two"])


class _ReplicateOutput:
    url = "https://example.test/audio.wav"

    def read(self):
        return b"audio"


class ReplicateRequestContractTests(unittest.TestCase):
    def test_ace_step_uses_a_30_second_duration_request(self):
        models = Mock()
        models.get.return_value.latest_version.id = "version-123"
        with tempfile.TemporaryDirectory() as tmp_dir, patch.object(
            replicate_music.replicate, "models", models
        ), patch.object(
            replicate_music.replicate, "run", return_value=_ReplicateOutput()
        ) as run:
            replicate_music.generate_ace_step_15(
                out_dir=tmp_dir, lyrics="lyrics", style="style", duration=30
            )

        run.assert_called_once_with(
            "fishaudio/ace-step-1.5:version-123",
            input={"prompt": "style", "lyrics": "lyrics", "duration": 30},
        )

    def test_stable_audio_uses_a_30_second_duration_request(self):
        with tempfile.TemporaryDirectory() as tmp_dir, patch.object(
            replicate_music.replicate, "run", return_value=_ReplicateOutput()
        ) as run:
            replicate_music.generate_stable_audio_25(
                out_dir=tmp_dir, lyrics="lyrics", style="style", duration=30
            )

        run.assert_called_once_with(
            "stability-ai/stable-audio-2.5",
            input={"prompt": "Style: style Lyrics: lyrics", "duration": 30},
        )


if __name__ == "__main__":
    unittest.main()
