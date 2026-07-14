# Running the backend on this MacBook

Status as of last check: **not set up yet**. Nothing below has been done on this
machine — no venv, no secrets file, no submodule checkout, no dependencies
installed. This doc is the checklist to get from zero to a running server.

## What's missing right now

- [ ] Python 3.11 (repo is tested against 3.11; this machine only has 3.13.14
      via `mise`, no 3.11 installed)
- [ ] `venv` — not created
- [ ] `backend/secrets.py` — does not exist (only `secrets.py.example` is committed)
- [ ] `demucs-mlx` git submodule — registered but checked out empty
- [ ] `~/.local/bin/demucs-mlx` binary — not installed
- [ ] Python dependencies (`pip install -r backend/requirements.txt`) — not installed
- [ ] `whisper` CLI — not on PATH (comes from `openai-whisper`, installed with the rest)

Already fine, no action needed:
- `ffmpeg` — present at `/opt/homebrew/bin/ffmpeg`

## Setup

```shell
# 1. Python 3.11, via mise (matches what the project is tested against)
mise install python@3.11
mise use -C /Users/ivan/proj/falai python@3.11   # or add a .mise.toml if you want it pinned

# 2. venv + Python deps
cd /Users/ivan/proj/falai
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. demucs-mlx submodule
git submodule update --init --recursive
cd demucs-mlx && make install && cd ..
# installs the demucs-mlx binary to ~/.local/bin/demucs-mlx (hardcoded path
# expected by backend/integrations/demucs.py)

# 4. Secrets
cp backend/secrets.py.example backend/secrets.py
# then edit backend/secrets.py and fill in real values for:
#   OPENROUTER_API_KEY
#   SUNO_API_KEY
#   FAL_API_KEY
#   REPLICATE_API_TOKEN
```

**Important:** `FAL_API_KEY` and `REPLICATE_API_TOKEN` must be present in
`backend/secrets.py` even if you don't intend to use those providers right
now. `backend/app.py` imports `music_provider`, which imports `fal_music`
and `replicate_music` at module load time, which do
`from backend.secrets import FAL_API_KEY` / `REPLICATE_API_TOKEN`
unconditionally — a missing name (not just an empty value) will raise
`ImportError` on startup regardless of which provider you actually use. An
empty string (`FAL_API_KEY=''`) is fine if you're not calling that path yet;
the value is only used the moment a request to that provider actually goes
out.

**Replicate note:** `replicate-ace-step-1.5` (fishaudio/ace-step-1.5) is
wired up and verified against a live generation. It's not an "official"
Replicate model, so predictions need a version-pinned reference
(`owner/name:version_id`) — the module resolves the latest version
dynamically at call time rather than hardcoding a hash.

## Running

```shell
cd /Users/ivan/proj/falai/backend
source ../venv/bin/activate
flask run --host=0.0.0.0 --port=5555 2>&1 | tee server.log
```

Sanity check in another terminal:
```shell
curl http://127.0.0.1:5555/health
# {"status": "ok"}
```

## Choosing the music provider

Default is Suno (unchanged behavior — no env var needed). To use fal.ai's
ACE-Step instead:

```shell
MUSIC_PROVIDER=fal flask run --host=0.0.0.0 --port=5555
```

Recommended: verify the fal.ai path standalone before running it through the
full pipeline, since it costs money per call and is easier to debug in
isolation:

```shell
python -m backend.integrations.fal_music \
  --lyrics "[Verse]\nWalking through the rain tonight\nCity lights are burning bright" \
  --style "dreampop, melancholic" \
  --out-dir /tmp/fal-test
```

Then exercise the full endpoint:
```shell
curl -X POST http://127.0.0.1:5555/generate-song \
  -H "Content-Type: application/json" \
  -d '{"input_message": "museum tonight? they got the new dali exhibition there", "genre": "edm"}'
```
(Or use the `Generate song` request in the `bruno/` collection with the
`localhost` environment selected.)

## Connecting the iOS client

`client/SoundsGoodCore/Services/MessageToSongServiceImpl.swift` has a
hardcoded `baseURL`:
```
https://nugget-freeing-grip.ngrok-free.dev
```
For the client to reach a backend running on this laptop, you need an ngrok
tunnel on that same hostname (if it's your reserved free static domain):
```shell
ngrok http 5555 --domain=nugget-freeing-grip.ngrok-free.dev
```
If that domain isn't actually reserved on your ngrok account (check
`ngrok config check` / the ngrok dashboard), a fresh `ngrok http 5555` will
mint a new random hostname — in that case update `baseURL` in
`MessageToSongServiceImpl.swift` to match before building the client.

## Known gaps not covered by this doc

- No automated tests exist in the repo to validate setup beyond manual
  curl/bruno checks.
- Python 3.13 vs the tested 3.11: not verified either way here — worth
  trying 3.11 first since that's what the README commits to.
