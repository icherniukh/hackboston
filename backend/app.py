import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request, send_file, Response

from backend.integrations.openrouter import generate_song_prompt
from backend.integrations.suno import generate_clip
from backend.integrations.demucs import separate_vocals
from backend.integrations.whisper import transcribe
from backend.integrations.ffmpeg import detect_lyrics_bounds, get_duration, trim
from backend.utils import mmssms_to_float_seconds

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


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

    # Generate lyrics + style_prompt
    prompt_result = generate_song_prompt(input_message=input_message, mood=mood, genre=genre)

    # Generate Suno song
    clip = generate_clip(
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        mood=mood,
        out_dir=song_dir,
    )
    song_path = clip.path

    # Extract voice stem and bounds + transcribe in parallel (both depend only on song_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        vocals_future = pool.submit(separate_vocals, song_path, output_dir=song_dir)
        transcript_future = pool.submit(transcribe, song_path)

        vocals_path = vocals_future.result()
        bounds_future = pool.submit(
            detect_lyrics_bounds, input_path=vocals_path, noise_threshold_db=-18
        )

    transcript = transcript_future.result()
    first_end, last_start = bounds_future.result()

    # Apply correct timestamps to transcription
    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")

    # Pad trim bounds, clamped to song duration
    song_duration = get_duration(song_path)
    trim_start = max(0.0, start_sec - 2)
    trim_end = min(song_duration, end_sec + 2)

    filtered_transcript = [
        entry for entry in transcript
        if mmssms_to_float_seconds(list(entry.keys())[0][0]) >= trim_start
        and mmssms_to_float_seconds(list(entry.keys())[0][1]) <= trim_end
    ]

    # Trim song to padded lyrics bounds, apply fade on both sides
    duration = trim_end - trim_start
    trimmed_path = os.path.join(song_dir, 'result.mp3')
    trim(src=song_path, dest=trimmed_path, duration_seconds=duration, start_seconds=trim_start, fade_seconds=1.0)

    # Serve
    serializable_transcript = [
        {"start": list(entry.keys())[0][0], "end": list(entry.keys())[0][1], "text": list(entry.values())[0]}
        for entry in filtered_transcript
    ]
    return jsonify({
        "input_message": input_message,
        "mood": mood,
        "lyrics": prompt_result["lyrics"],
        "style_prompt": prompt_result["style_prompt"],
        "transcript": serializable_transcript,
        "result_url": f"/songs/{song_id}.mp3",
    })


@app.route("/songs/<song_id>.mp3")
def stream_song(song_id):
    filepath = os.path.join(OUTPUT_DIR, song_id, 'result.mp3')
    if not os.path.exists(filepath):
        return Response(status=404)
    return send_file(filepath, mimetype="audio/mpeg")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
