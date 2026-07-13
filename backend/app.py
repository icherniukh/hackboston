import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from flask import Flask, jsonify, request, send_file, Response

from backend.integrations.openrouter import generate_song_prompt, generate_reply_context, generate_album_art
from backend.integrations.music_provider import generate_clip
from backend.integrations.demucs import separate_vocals
from backend.integrations.ffmpeg import detect_lyrics_bounds, get_duration, trim, attach_cover
from backend.utils import mmssms_to_float_seconds

logger = logging.getLogger(__name__)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# In-memory tracking for reply song jobs: song_id -> {event, result}
reply_jobs: dict[str, dict] = {}


def _postprocess_song(song_path: str, song_dir: str, t0: float) -> None:
    vocals_path = separate_vocals(song_path, output_dir=song_dir)
    logger.info("[%+.1fs] demucs done", time.monotonic() - t0)

    first_end, last_start = detect_lyrics_bounds(input_path=vocals_path, noise_threshold_db=-7)
    logger.info("[%+.1fs] lyrics bounds detected", time.monotonic() - t0)

    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")

    song_duration = get_duration(song_path)
    trim_start = max(0.0, start_sec - 2)
    trim_end = min(song_duration, end_sec + 2)

    duration = trim_end - trim_start
    trimmed_path = os.path.join(song_dir, "trimmed.mp3")
    trim(
        src=song_path,
        dest=trimmed_path,
        duration_seconds=duration,
        start_seconds=trim_start,
        fade_seconds=1.0,
    )
    logger.info("[%+.1fs] trim done", time.monotonic() - t0)


def _produce_song(
    *,
    prompt_result: dict,
    input_message: str,
    song_id: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    t0: float = 0.0,
) -> dict:
    """Generate a Suno clip, post-process, generate album art, and persist the response.

    Returns response_dict.
    """
    song_id = song_id or str(uuid.uuid4())
    song_dir = os.path.join(OUTPUT_DIR, song_id)
    os.makedirs(song_dir, exist_ok=True)

    pool = ThreadPoolExecutor(max_workers=2)
    song_future = pool.submit(generate_clip,
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        out_dir=song_dir,
    )
    art_future = pool.submit(generate_album_art,
        input_message=input_message,
        out_dir=song_dir,
    )
    logger.info("[%+.1fs] clip+art submitted", time.monotonic() - t0)

    clip = song_future.result()
    logger.info("[%+.1fs] clip ready", time.monotonic() - t0)

    _postprocess_song(clip.path, song_dir, t0)

    cover_path = art_future.result()
    pool.shutdown(wait=False)
    logger.info("[%+.1fs] art ready", time.monotonic() - t0)

    # Convert PNG cover to JPG for m4a embedding
    cover_jpg = os.path.join(song_dir, "cover.jpg")
    Image.open(cover_path).convert("RGB").save(cover_jpg, "JPEG")
    logger.info("[%+.1fs] cover converted to JPG", time.monotonic() - t0)

    # Combine audio + cover into m4a
    m4a_path = os.path.join(song_dir, "result.m4a")
    attach_cover(
        audio_path=os.path.join(song_dir, "trimmed.mp3"),
        cover_path=cover_jpg,
        dest=m4a_path,
    )
    logger.info("[%+.1fs] m4a assembled", time.monotonic() - t0)

    response = {
        "id": song_id,
        "input_message": input_message,
        "mood": mood,
        "genre": genre,
        "lyrics": prompt_result["lyrics"],
        "style_prompt": prompt_result["style_prompt"],
        "result_url": f"/songs/{song_id}.m4a",
    }
    with open(os.path.join(song_dir, "response.json"), "w") as f:
        json.dump(response, f, indent=2)

    return response


@app.route("/generate-song", methods=["POST"])
def generate_song_endpoint():
    t0 = time.monotonic()
    data = request.get_json(force=True)
    input_message = data.get("input_message")
    if not input_message:
        return jsonify({"error": "No input message provided"}), 400
    mood = data.get("mood")
    genre = data.get("genre")

    song_id = str(uuid.uuid4())

    # Set up reply job tracking before starting anything
    reply_event = threading.Event()
    reply_jobs[song_id] = {"event": reply_event, "result": None}
    original_suno_done = threading.Event()

    def run_reply_pipeline():
        try:
            reply_context = generate_reply_context(original_lyrics=prompt_result["lyrics"])
            reply_prompt = generate_song_prompt(
                input_message=reply_context["input_message"],
                genre=reply_context["genre"],
            )
            original_suno_done.wait()

            reply_jobs[song_id]["result"] = _produce_song(
                prompt_result=reply_prompt,
                input_message=reply_context["input_message"],
                mood=reply_context.get("mood"),
                genre=reply_context.get("genre"),
            )
        except Exception as e:
            reply_jobs[song_id]["result"] = {"error": str(e)}
        finally:
            reply_event.set()

    # Original OpenRouter (lyrics + style_prompt)
    prompt_result = generate_song_prompt(input_message=input_message, mood=mood, genre=genre)
    logger.info("[%+.1fs] song prompt generated", time.monotonic() - t0)

    # Kick off reply pipeline — its OpenRouter calls run while original Suno generates
    # threading.Thread(target=run_reply_pipeline, daemon=True).start()

    # Original Suno + postprocess
    response = _produce_song(
        prompt_result=prompt_result,
        input_message=input_message,
        song_id=song_id,
        mood=mood,
        genre=genre,
        t0=t0,
    )
    original_suno_done.set()

    logger.info("[%+.1fs] endpoint complete", time.monotonic() - t0)
    return jsonify(response)


@app.route("/expect-reply", methods=["POST"])
def expect_reply_endpoint():
    data = request.get_json(force=True)
    reference_id = data.get("reference_id")
    if not reference_id:
        return jsonify({"error": "No reference_id provided"}), 400

    job = reply_jobs.get(reference_id)
    if not job:
        return jsonify({"error": "No reply job found for this reference_id"}), 404

    # Block until the reply pipeline is done
    job["event"].wait()
    result = job["result"]
    if result and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@app.route("/songs/<song_id>.m4a")
def stream_song(song_id):
    filepath = os.path.join(OUTPUT_DIR, song_id, "result.m4a")
    if not os.path.exists(filepath):
        return Response(status=404)
    return send_file(filepath, mimetype="audio/mp4")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5555)
