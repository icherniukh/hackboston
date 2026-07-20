"""Contract tests for provider selection and capabilities."""

from __future__ import annotations

import types
import unittest
import inspect
from unittest.mock import Mock, patch

from backend.integrations import music_provider
from backend.integrations import fal_music, runware_music, suno


class MusicProviderTests(unittest.TestCase):
    def test_unsupported_duration_is_not_exposed_by_provider_adapters(self):
        unsupported = [
            suno.generate_clip,
            fal_music.generate_minimax_v2,
            fal_music.generate_minimax_v25,
            fal_music.generate_minimax_v26,
            fal_music.generate_lyria3,
            runware_music.generate_runware,
        ]

        for generate in unsupported:
            with self.subTest(generate=generate.__name__):
                self.assertNotIn("duration", inspect.signature(generate).parameters)

    def test_dispatch_loads_only_the_selected_provider_and_filters_unsupported_duration(self):
        if not hasattr(music_provider, "provider_capabilities"):
            self.fail("music_provider must expose provider-owned capabilities")

        generate = Mock(return_value="clip")
        module = types.SimpleNamespace(generate_clip=generate)
        with patch.object(music_provider, "import_module", return_value=module) as load:
            result = music_provider.generate_clip(
                out_dir="/tmp/out",
                provider="suno",
                lyrics="lyrics",
                style="style",
                duration=30,
            )

        self.assertEqual(result, "clip")
        load.assert_called_once_with("backend.integrations.suno")
        generate.assert_called_once_with(
            out_dir="/tmp/out", lyrics="lyrics", style="style"
        )
        self.assertFalse(music_provider.provider_capabilities("suno").supports_duration)

    def test_dispatch_passes_duration_only_to_a_provider_that_supports_it(self):
        if not hasattr(music_provider, "provider_capabilities"):
            self.fail("music_provider must expose provider-owned capabilities")

        generate = Mock(return_value="clip")
        module = types.SimpleNamespace(generate_ace_step=generate)
        with patch.object(music_provider, "import_module", return_value=module) as load:
            music_provider.generate_clip(
                out_dir="/tmp/out",
                provider="ace-step",
                lyrics="lyrics",
                style="style",
                duration=30,
            )

        load.assert_called_once_with("backend.integrations.fal_music")
        generate.assert_called_once_with(
            out_dir="/tmp/out", lyrics="lyrics", style="style", duration=30
        )
        self.assertTrue(music_provider.provider_capabilities("ace-step").supports_duration)

    def test_playback_url_is_delegated_to_the_provider(self):
        if not hasattr(music_provider, "mint_playback_url"):
            self.fail("music_provider must delegate source playback to providers")

        mint = Mock(return_value="https://example.test/playback")
        module = types.SimpleNamespace(mint_playback_url=mint)
        with patch.object(music_provider, "import_module", return_value=module):
            url = music_provider.mint_playback_url("suno", "clip-123")

        self.assertEqual(url, "https://example.test/playback")
        mint.assert_called_once_with("clip-123")


if __name__ == "__main__":
    unittest.main()
