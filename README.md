## Backend

### Operating instructions
Prep (tested on Python 3.11):
```shell
python3 -m venv venv
cd backend && pip install -r requirements.txt
cd ../demucs-mlx && make install && cd ..
```
Run:
```shell
cd backend
flask run --host=0.0.0.0 --port=5555 2>&1 | tee server.log
ngrok http 5555  # For public endpoint access
```

### Milestone 1 – Song generation
- [x] LLM integration
	- Model: Gemma-4
	- [x] Coming up with the lyrics
	- [ ] (?) Finding the best slice from the transcript
- [x] Suno integration
- [x] Stemming
- [x] Transcribing
  - [ ] Idea: try removing the transcription part and trimming to any vocals
- [x] Silence scanning

```mermaid
flowchart TD
    A0["<b>POST /generate-song</b><br>Receive input message and optional desired mood & genre"]
    A["gemma-4-31b-it (via OpenRouter)<br><b>generate lyrics and style prompt</b>"] --> B1
    A0 --> A
    A --> B2

    subgraph parallel["Thread pool (2 workers)"]
        B1["<b>Suno /v0/audio API<br>generate song</b>"]
        B2["gemini-3.1-flash-image-preview<br>(via OpenRouter) produce album art"]
    end

    B1 --> C0["ffmpeg: MP3 → WAV for demucs input"]
    C0 --> C["demucs-mlx: separate the vocals stem"]
    C --> D["ffmpeg: detect vocals bounds via silencedetect filter"]
    B2 --> F["Pillow: PNG → JPG<br>(for filesize savings)"]
    D & F --> G["ffmpeg trim, fade & attach cover"]
    G --> H["Serve as <b>GET /songs/&lt;id&gt;.m4a</b>"]
```

### Milestone 2 – Backend response
- [ ] `expect-response` client poll API taking the reference uuid

```mermaid
sequenceDiagram
    participant Client
    participant Server

    Client->>+Server: /generate-song
    Note right of Server: Processes song (~50 seconds), immediately<br>starts processing a new song in response to it<br>step by step as soon as it can be done
    Server->>Client: Sends generated song
    Client->>Server: /expect-response
    Note right of Server: Finishes processing response
    Server->>-Client: Sends response
```

### Presentation
- [ ] Showcase a11y
- [ ] Mention postcards
- [ ] Mention iMessage
