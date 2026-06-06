import os

from flask import Flask, jsonify, request, send_file, Response
import uuid

from backend.integrations.openrouter import generate_song_prompt
from backend.integrations.suno import generate_clip
from backend.integrations.demucs import separate_vocals
from backend.integrations.whisper import transcribe
from backend.integrations.ffmpeg import detect_lyrics_bounds, trim
from backend.utils import mmssms_to_float_seconds

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/generate-song", methods=["POST"])
def generate_song_endpoint():
    data = request.get_json(force=True)
    input_message = data.get("input_message", "")
    mood = data.get("mood", "neutral")

    song_id = str(uuid.uuid4())
    song_dir = os.path.join(OUTPUT_DIR, song_id)
    os.makedirs(song_dir, exist_ok=True)

    # Generate lyrics + style_prompt
    prompt_result = generate_song_prompt(input_message=input_message, mood=mood)

    # Generate Suno song
    clip = generate_clip(
        lyrics=prompt_result["lyrics"],
        style=prompt_result["style_prompt"],
        mood=mood,
        out_dir=song_dir,
    )
    song_path = clip.path

    # Extract voice stem (demucs)
    vocals_path = separate_vocals(song_path)

    # Transcribe song (whisper)
    transcript = transcribe(song_path)

    # Extract lyrics start & end timestamps from vocals
    first_end, last_start = detect_lyrics_bounds(
        input_path=vocals_path, noise_threshold_db=-18
    )

    # Apply correct timestamps to transcription
    start_sec = mmssms_to_float_seconds(first_end) if first_end else 0.0
    end_sec = mmssms_to_float_seconds(last_start) if last_start else float("inf")
    filtered_transcript = [
        entry for entry in transcript
        if mmssms_to_float_seconds(list(entry.keys())[0][0]) >= start_sec
        and mmssms_to_float_seconds(list(entry.keys())[0][1]) <= end_sec
    ]

    # Trim song to lyrics bounds
    duration = end_sec - start_sec
    trimmed_path = os.path.join(song_dir, 'result.mp3')
    trim(song_path, trimmed_path, duration, start=start_sec)

    # Serve
    return jsonify({
        "input_message": input_message,
        "mood": mood,
        "lyrics": prompt_result["lyrics"],
        "style_prompt": prompt_result["style_prompt"],
        "transcript": filtered_transcript,
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
