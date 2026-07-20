import json
import logging
import mimetypes
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from flask import Flask, jsonify, redirect, request, send_file, Response

from backend.integrations.openrouter import generate_song_prompt, generate_reply_context, generate_album_art
from backend.integrations.music_provider import (
    generate_clip,
    mint_playback_url,
    provider_capabilities,
    resolve_provider,
)
from backend.integrations.demucs import separate_vocals
from backend.integrations.ffmpeg import detect_lyrics_bounds, get_duration, trim, attach_cover
from backend.utils import mmssms_to_float_seconds

logger = logging.getLogger(__name__)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# In-memory tracking for reply song jobs: song_id -> {event, result}
reply_jobs: dict[str, dict] = {}


def _postprocess_song(song_path: str, song_dir: str, t0: float) -> None:
    vocals_path = separate_vocals(song_path, output_dir=song_dir)
    logger.info("[%+.1fs] demucs done", time.monotonic() - t0)

    # -7dB was misclassifying most of the actual singing as silence: demucs
    # vocal stems in practice sit around -20 to -23dB mean volume (checked
    # across several real generations), so nearly everything but the
    # loudest peaks fell below a -7dB bar and got trimmed away.
    first_end, last_start = detect_lyrics_bounds(input_path=vocals_path, noise_threshold_db=-30)
    logger.info("[%+.1fs] lyrics bounds detected", time.monotonic() - t0)

    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")

    song_duration = get_duration(song_path)
    trim_start = max(0.0, start_sec - 2)
    trim_end = min(song_duration, end_sec + 2)

    fade_seconds = 1.0
    duration = trim_end - trim_start
    if duration <= fade_seconds:
        # Vocal bounds detection found no clear window (e.g. inverted or
        # near-zero span) — fall back to the untrimmed clip rather than
        # handing ffmpeg a fade longer than the clip itself.
        trim_start, duration = 0.0, song_duration

    trimmed_path = os.path.join(song_dir, "trimmed.mp3")
    trim(
        src=song_path,
        dest=trimmed_path,
        duration_seconds=duration,
        start_seconds=trim_start,
        fade_seconds=fade_seconds,
    )
    logger.info("[%+.1fs] trim done", time.monotonic() - t0)


def _produce_song(
    *,
    prompt_result: dict,
    input_message: str,
    song_id: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    music_model: str | None = None,
    t0: float = 0.0,
) -> dict:
    """Generate a music clip, post-process, generate album art, and persist the response.

    Returns response_dict.
    """
    song_id = song_id or str(uuid.uuid4())
    song_dir = os.path.join(OUTPUT_DIR, song_id)
    os.makedirs(song_dir, exist_ok=True)
    provider_id, _ = resolve_provider(music_model)

    pool = ThreadPoolExecutor(max_workers=2)
    song_future = pool.submit(generate_clip,
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        provider=provider_id,
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
    source = {
        "provider": provider_id,
        "clip_id": clip.id,
        "file_name": os.path.basename(clip.path),
        "local_url": f"/songs/{song_id}/source",
    }
    if provider_capabilities(provider_id).supports_playback_url and clip.id:
        source["playback_url"] = f"/songs/{song_id}/source/playback"
    response["source"] = source
    with open(os.path.join(song_dir, "response.json"), "w") as f:
        json.dump(response, f, indent=2)

    return response


@app.route("/")
def index():
    return send_file(os.path.join(STATIC_DIR, "index.html"))


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
                music_model=music_model,
            )
        except Exception as e:
            reply_jobs[song_id]["result"] = {"error": str(e)}
        finally:
            reply_event.set()

    # Original OpenRouter (lyrics + style_prompt)
    lyrics_model = data.get("lyrics_model")
    music_model = data.get("music_model")
    prompt_result = generate_song_prompt(input_message=input_message, mood=mood, genre=genre, model=lyrics_model)
    logger.info("[%+.1fs] song prompt generated", time.monotonic() - t0)

    # Kick off reply pipeline — its OpenRouter calls run while original Suno generates
    # threading.Thread(target=run_reply_pipeline, daemon=True).start()

    try:
        response = _produce_song(
            prompt_result=prompt_result,
            input_message=input_message,
            song_id=song_id,
            mood=mood,
            genre=genre,
            music_model=music_model,
            t0=t0,
        )
    except Exception as e:
        logger.exception("Error producing song")
        return jsonify({"error": str(e)}), 500

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


def _load_source_metadata(song_id: str) -> dict | None:
    """Read a persisted source-artifact manifest without trusting file paths."""
    metadata_path = os.path.join(OUTPUT_DIR, song_id, "response.json")
    try:
        with open(metadata_path) as metadata_file:
            source = json.load(metadata_file).get("source")
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(source, dict):
        return None
    file_name = source.get("file_name")
    if not isinstance(file_name, str) or file_name != os.path.basename(file_name):
        return None
    return source


@app.route("/songs/<song_id>/source")
def stream_source(song_id):
    """Serve the unprocessed provider artifact retained for analysis."""
    source = _load_source_metadata(song_id)
    if source is None:
        return Response(status=404)
    filepath = os.path.join(OUTPUT_DIR, song_id, source["file_name"])
    if not os.path.exists(filepath):
        return Response(status=404)
    mimetype, _ = mimetypes.guess_type(filepath)
    return send_file(filepath, mimetype=mimetype or "application/octet-stream")


@app.route("/songs/<song_id>/source/playback")
def open_source_playback(song_id):
    """Redirect to a fresh provider-managed source playback URL."""
    source = _load_source_metadata(song_id)
    if source is None or not source.get("clip_id"):
        return Response(status=404)

    try:
        return redirect(mint_playback_url(source["provider"], source["clip_id"]))
    except ValueError:
        return Response(status=404)
    except Exception:
        logger.exception("Could not mint source playback URL for %s", song_id)
        return jsonify({"error": "Could not mint source playback URL"}), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5555)
