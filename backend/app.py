import json
import os
import threading
import uuid

from flask import Flask, jsonify, request, send_file, Response

from backend.integrations.openrouter import generate_song_prompt, generate_reply_context
from backend.integrations.suno import generate_clip
from backend.integrations.demucs import separate_vocals
from backend.integrations.ffmpeg import detect_lyrics_bounds, get_duration, trim
from backend.utils import mmssms_to_float_seconds

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# In-memory tracking for reply song jobs: song_id -> {event, result}
reply_jobs: dict[str, dict] = {}


def _postprocess_song(song_path: str, song_dir: str) -> None:
    vocals_path = separate_vocals(song_path, output_dir=song_dir)
    first_end, last_start = detect_lyrics_bounds(input_path=vocals_path, noise_threshold_db=-18)

    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")

    song_duration = get_duration(song_path)
    trim_start = max(0.0, start_sec - 2)
    trim_end = min(song_duration, end_sec + 2)

    duration = trim_end - trim_start
    trimmed_path = os.path.join(song_dir, "result.mp3")
    trim(
        src=song_path,
        dest=trimmed_path,
        duration_seconds=duration,
        start_seconds=trim_start,
        fade_seconds=1.0,
    )


def _produce_song(
    *,
    prompt_result: dict,
    input_message: str,
    song_id: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
) -> dict:
    """Generate a Suno clip, post-process, and persist the response.

    Returns (song_id, response_dict).
    """
    song_id = song_id or str(uuid.uuid4())
    song_dir = os.path.join(OUTPUT_DIR, song_id)
    os.makedirs(song_dir, exist_ok=True)

    clip = generate_clip(
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        out_dir=song_dir,
    )

    _postprocess_song(clip.path, song_dir)

    response = {
        "id": song_id,
        "input_message": input_message,
        "mood": mood,
        "genre": genre,
        "lyrics": prompt_result["lyrics"],
        "style_prompt": prompt_result["style_prompt"],
        "result_url": f"/songs/{song_id}.mp3",
    }
    with open(os.path.join(song_dir, "response.json"), "w") as f:
        json.dump(response, f, indent=2)

    return response


@app.route("/generate-song", methods=["POST"])
def generate_song_endpoint():
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

    # Kick off reply pipeline — its OpenRouter calls run while original Suno generates
    # threading.Thread(target=run_reply_pipeline, daemon=True).start()

    # Original Suno + postprocess
    response = _produce_song(
        prompt_result=prompt_result,
        input_message=input_message,
        song_id=song_id,
        mood=mood,
        genre=genre,
    )
    original_suno_done.set()

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


@app.route("/songs/<song_id>.mp3")
def stream_song(song_id):
    filepath = os.path.join(OUTPUT_DIR, song_id, "result.mp3")
    if not os.path.exists(filepath):
        return Response(status=404)
    return send_file(filepath, mimetype="audio/mpeg")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5555)
