"""Contract tests for the Runware audio request payload."""

from __future__ import annotations

import inspect
import unittest

from backend.integrations import runware_music


class RunwareRequestTests(unittest.TestCase):
    def test_request_uses_only_documented_adapter_inputs(self):
        if not hasattr(runware_music, "build_audio_inference_request"):
            self.fail("Runware payload construction must be explicit and testable")

        request = runware_music.build_audio_inference_request(
            task_id="task-123",
            model="runware:ace-step@v1.5-xl-sft",
            lyrics="Only these words",
            style="Dream pop",
        )

        self.assertEqual(
            request,
            {
                "taskType": "audioInference",
                "taskUUID": "task-123",
                "model": "runware:ace-step@v1.5-xl-sft",
                "positivePrompt": "Style: Dream pop\nLyrics: Only these words",
            },
        )
        self.assertNotIn("duration", inspect.signature(runware_music.generate_runware).parameters)


if __name__ == "__main__":
    unittest.main()
