from flask import Flask, request, jsonify, Response
import uuid

app = Flask(__name__)

@app.route("/generate-song", methods=["POST"])
def generate_song():
    data = request.get_json(force=True)
    input_message = data.get("input_message", "")
    mood = data.get("mood", "neutral")

    song_id = str(uuid.uuid4())

    # TODO: generate actual audio and store it
    return jsonify({
        "song_id": song_id,
        "input_message": input_message,
        "mood": mood,
        "download_url": f"/songs/{song_id}.wav",
        "stream_url": f"/songs/{song_id}.wav",
        "status": "ready"
    })

@app.route("/songs/<song_id>.wav")
def stream_song(song_id):
    # TODO: return actual audio stream from storage
    return Response(status=204)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
