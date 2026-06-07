import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request, send_file, Response

from backend.integrations.openrouter import generate_song_prompt, generate_reply_context
from backend.integrations.suno import generate_clip
from backend.integrations.demucs import separate_vocals
from backend.integrations.whisper import transcribe
from backend.integrations.ffmpeg import detect_lyrics_bounds, get_duration, trim
from backend.utils import mmssms_to_float_seconds

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# In-memory tracking for reply song jobs: song_id -> {event, result}
reply_jobs: dict[str, dict] = {}


def _postprocess_song(song_path: str, song_dir: str) -> dict:
    """Run demucs, whisper, bounds detection, trim, and fade on a generated clip.
    Returns {"transcript": [...], "trim_start": float, "trim_end": float, "duration": float}.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        vocals_future = pool.submit(separate_vocals, song_path, output_dir=song_dir)
        transcript_future = pool.submit(transcribe, song_path)

        vocals_path = vocals_future.result()
        bounds_future = pool.submit(
            detect_lyrics_bounds, input_path=vocals_path, noise_threshold_db=-18
        )

    transcript = transcript_future.result()
    first_end, last_start = bounds_future.result()

    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")

    song_duration = get_duration(song_path)
    trim_start = max(0.0, start_sec - 2)
    trim_end = min(song_duration, end_sec + 2)

    filtered_transcript = [
        entry for entry in transcript
        if mmssms_to_float_seconds(list(entry.keys())[0][0]) >= trim_start
        and mmssms_to_float_seconds(list(entry.keys())[0][1]) <= trim_end
    ]

    duration = trim_end - trim_start
    trimmed_path = os.path.join(song_dir, "result.mp3")
    trim(
        src=song_path,
        dest=trimmed_path,
        duration_seconds=duration,
        start_seconds=trim_start,
        fade_seconds=1.0,
    )

    serializable_transcript = [
        {
            "start": list(entry.keys())[0][0],
            "end": list(entry.keys())[0][1],
            "text": list(entry.values())[0],
        }
        for entry in filtered_transcript
    ]
    return {
        "transcript": serializable_transcript,
        "trim_start": trim_start,
        "trim_end": trim_end,
        "duration": duration,
    }


@app.route("/generate-song", methods=["POST"])
def generate_song_endpoint():
    data = request.get_json(force=True)
    input_message = data.get("input_message")
    if not input_message:
        return jsonify({"error": "No input message provided"}), 400
    mood = data.get("mood")
    genre = data.get("genre")

    song_id = str(uuid.uuid4())
    song_dir = os.path.join(OUTPUT_DIR, song_id)
    os.makedirs(song_dir, exist_ok=True)

    # Set up reply job tracking
    reply_event = threading.Event()
    reply_jobs[song_id] = {"event": reply_event, "result": None}
    original_suno_done = threading.Event()

    def run_reply_pipeline():
        try:
            # R1: Generate reply context (input_message, mood, genre) via OpenRouter
            reply_context = generate_reply_context(input_message, prompt_result)

            # R2: Generate reply song prompt (lyrics, style_prompt) via OpenRouter
            reply_prompt = generate_song_prompt(
                input_message=reply_context["input_message"],
                mood=reply_context["mood"],
                genre=reply_context["genre"],
            )

            # R3: Wait for original Suno to finish, then start reply Suno
            original_suno_done.wait()

            reply_song_id = str(uuid.uuid4())
            reply_song_dir = os.path.join(OUTPUT_DIR, reply_song_id)
            os.makedirs(reply_song_dir, exist_ok=True)

            reply_clip = generate_clip(
                lyrics=reply_prompt["lyrics"],
                style=reply_prompt["style_prompt"],
                mood=reply_context["mood"],
                out_dir=reply_song_dir,
            )

            # R4: Full post-processing (runs while original demucs/whisper may still be going)
            pp = _postprocess_song(reply_clip.path, reply_song_dir)

            reply_response = {
                "reference_id": song_id,
                "input_message": reply_context["input_message"],
                "mood": reply_context["mood"],
                "genre": reply_context["genre"],
                "lyrics": reply_prompt["lyrics"],
                "style_prompt": reply_prompt["style_prompt"],
                "transcript": pp["transcript"],
                "result_url": f"/songs/{reply_song_id}.mp3",
            }
            with open(os.path.join(reply_song_dir, "response.json"), "w") as f:
                json.dump(reply_response, f, indent=2)

            reply_jobs[song_id]["result"] = reply_response
        except Exception as e:
            reply_jobs[song_id]["result"] = {"error": str(e)}
        finally:
            reply_event.set()

    # Step 1: Original OpenRouter (lyrics + style_prompt)
    prompt_result = generate_song_prompt(input_message=input_message, mood=mood, genre=genre)

    # Kick off reply pipeline in background — OpenRouter calls run while original Suno generates
    reply_thread = threading.Thread(target=run_reply_pipeline, daemon=True)
    reply_thread.start()

    # Step 2: Original Suno (blocking)
    clip = generate_clip(
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        mood=mood,
        out_dir=song_dir,
    )
    song_path = clip.path
    original_suno_done.set()  # Reply pipeline can now start its Suno call

    # Step 3: Original post-processing
    pp = _postprocess_song(song_path, song_dir)

    response = {
        "id": song_id,
        "input_message": input_message,
        "mood": mood,
        "genre": genre,
        "lyrics": prompt_result["lyrics"],
        "style_prompt": prompt_result["style_prompt"],
        "transcript": pp["transcript"],
        "result_url": f"/songs/{song_id}.mp3",
    }
    with open(os.path.join(song_dir, "response.json"), "w") as f:
        json.dump(response, f, indent=2)
    return jsonify(response)


@app.route("/expect-reply", methods=["POST"])
def expect_reply_endpoint():
    data = request.get_json(force=True)
    reference_id = data.get("reference-id")
    if not reference_id:
        return jsonify({"error": "No reference-id provided"}), 400

    job = reply_jobs.get(reference_id)
    if not job:
        return jsonify({"error": "No reply job found for this reference-id"}), 404

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
    app.run(debug=True, port=5000)
