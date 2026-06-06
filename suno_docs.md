# Quickstart

A short guide to generating music through Suno's public API. Covers authentication, the four generation modes (Simple, Custom, Cover, Mashup), and how to attach one of our preset voices.

---

## Prerequisite

You need to have a Suno account that can use Google to login.

![][image1]

Contact Suno for access to the online portal [platform.suno.com](http://platform.suno.com). You need to provide the email address you used for Suno login. 

---

## Online Portal

Once an external API account is set up for you, you should be able to login [platform.suno.com](http://platform.suno.com) with your suno account email via Google OAuth. You should be able to view plans, current usage, and manage secret keys for API access. Create an API key and use it as a bearer token in your request’s `Authorization` header.

---

## Base URL

`https://api.suno.com/`  
---

## Authentication

Every request must include your API key in the `Authorization` header:

```
Authorization: Bearer <secret_key>
```

Keys should look like `sk_live_` followed by 64 hex characters. Treat them as secrets — do not check them into source control or expose them in client-side code. Rotate them through the Suno platform console. Key management will be available soon

---

## Generation Flow

All generation endpoints are asynchronous:

1. `POST` to the generation endpoint → returns `{ "id", "status": "submitted" }`  
2. Poll `GET /v0/audio/{id}` until `status` is `"complete"` (or `"error"`)  
3. When `status` is `"streaming"` or `"complete"`, `audio_url` is populated

Typical wall-clock time from submit to `complete` is under a minute.

### Status values

| Status | Meaning |
| :---- | :---- |
| `submitted` | Accepted; job has not started yet |
| `queued` | Waiting to start |
| `streaming` | Partial audio is available at `audio_url` (live progressive stream) |
| `complete` | Final CDN URL is available at `audio_url` |
| `error` | Failed; see `error` field |

---

## Preset Voice IDs

Custom voice cloning is not yet open to partners. You can pass any one of these three preset voice UUIDs in the optional `voice_id` field. Omitting `voice_id` lets the model pick a voice based on style and lyrics.

| `voice_id` | Description |
| :---- | :---- |
| `5b915c6d-8d96-416c-9755-eba65868cfef` | Preset voice A (female voice) |
| `c036ce3a-55e4-4690-9b8d-4516b37a96d5` | Preset voice B (weird kid voice) |
| `27f5465b-73c3-4134-b11e-70b0bd571c6c` | Preset voice C (low male voice) |

Any other value returns `400 Bad Request` with `{"error":"custom voice is not currently supported"}`.

---

## 1\. Simple mode — `POST /v0/audio` with `description`

Let the model generate both the lyrics and the style from a single natural-language prompt. Do **not** combine `description` with `style` — the API will reject it.

### 1a. Simple, no voice

```shell
curl -X POST https://api.suno.com/v0/audio \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "upbeat synthwave track about driving through Tokyo at night",
    "title": "Neon Drive"
  }'
```

### 1b. Simple, with preset voice

```shell
curl -X POST https://api.suno.com/v0/audio \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "upbeat synthwave track about driving through Tokyo at night",
    "title": "Neon Drive",
    "voice_id": "5b915c6d-8d96-416c-9755-eba65868cfef"
  }'
```

Response (both):

```json
{
  "id": "6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08",
  "status": "submitted",
  "created_at": "2026-04-20T18:03:11Z"
}
```

---

## 2\. Custom mode — `POST /v0/audio` with `lyrics` \+ `style`

Supply your own lyrics and a style string. `title` is optional.

### 2a. Custom, no voice

```shell
curl -X POST https://api.suno.com/v0/audio \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "lyrics": "[Verse]\nWalking through the static glow\nEvery street a radio\n[Chorus]\nWe are the signal, we are the noise",
    "style": "dreampop, reverb-heavy guitars, melancholic",
    "title": "Signal & Noise"
  }'
```

### 2b. Custom, with preset voice

```shell
curl -X POST https://api.suno.com/v0/audio \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "lyrics": "[Verse]\nWalking through the static glow\nEvery street a radio\n[Chorus]\nWe are the signal, we are the noise",
    "style": "dreampop, reverb-heavy guitars, melancholic",
    "title": "Signal & Noise",
    "voice_id": "c036ce3a-55e4-4690-9b8d-4516b37a96d5"
  }'
```

### Instrumental (no vocals)

Set `instrumental: true`. Lyrics and description are then optional.

```shell
curl -X POST https://api.suno.com/v0/audio \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "style": "lo-fi hip hop, mellow piano, rainy night",
    "title": "Study Beats",
    "instrumental": true
  }'
```

---

## 3\. Cover mode — `POST /v0/audio/{id}/covers`

Re-generate an existing clip you own, optionally with new lyrics, new style, and/or a different voice. The `{id}` in the path is the `id` of a clip returned by a prior `POST /v0/audio` call.

The lyrics, style, and voice are all optional. Leave `lyrics` empty to produce an instrumental cover.

### 3a. Cover, no voice (new style only)

```shell
curl -X POST https://api.suno.com/v0/audio/6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08/covers \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "style": "acoustic folk, fingerpicked guitar"
  }'
```

### 3b. Cover, with preset voice and new lyrics

```shell
curl -X POST https://api.suno.com/v0/audio/6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08/covers \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "lyrics": "[Verse]\nNew words over the same melody\n[Chorus]\nSame song, different story",
    "style": "acoustic folk, fingerpicked guitar",
    "voice_id": "27f5465b-73c3-4134-b11e-70b0bd571c6c"
  }'
```

---

## 4\. Mashup mode — `POST /v0/audio/{id}/mashups`

Blend two clips you own into a new track. The `{id}` in the path is one parent (the "source"); pass the second parent in `additional_audio_id`. Voice conditioning (`voice_id`) is **not** supported on mashups.

`lyrics` and `style` are optional. Leave `lyrics` empty to produce an instrumental mashup. If you omit `title`, it defaults to `"<source title> x <additional title> (Mashup)"`.

```shell
curl -X POST https://api.suno.com/v0/audio/6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08/mashups \
  -H "Authorization: Bearer sk_live_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "additional_audio_id": "9a9e1da2-cf97-46bc-9b07-eaa2290fcba0",
    "lyrics": "[Verse]\nTwo songs braided into one\n[Chorus]\nNew shape, same heart",
    "style": "trap meets folk"
  }'
```

## ---

## 5\. Polling — `GET /v0/audio/{id}`

```shell
curl https://api.suno.com/v0/audio/6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08 \
  -H "Authorization: Bearer sk_live_<your-key>"
```

Response while still generating:

```json
{
  "id": "6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08",
  "status": "queued",
  "audio_url": "",
  "title": "Neon Drive",
  "created_at": "2026-04-20T18:03:11Z",
  "error": null,
  "metadata": {
    "lyrics": null,
    "style": null,
    "description": "upbeat synthwave track about driving through Tokyo at night"
  }
}
```

Response once complete:

```json
{
  "id": "6e2b0f3a-1c5d-4a2e-9f81-7c11f9e24b08",
  "status": "complete",
  "audio_url": "https://cdn.suno.ai/.../audio.mp3",
  "title": "Neon Drive",
  "created_at": "2026-04-20T18:03:11Z",
  "error": null,
  "metadata": {
    "lyrics": "[Verse]\n...",
    "style": "synthwave, driving, neon",
    "description": "upbeat synthwave track about driving through Tokyo at night"
  }
}
```

`voice_id`, `cover_audio_id`, and `mashup_clip_ids` are clip-type-scoped: each appears in `metadata` only when set. `voice_id` is populated when a preset voice was used. `cover_audio_id` appears on cover clips and points at the source clip. `mashup_clip_ids` appears on mashup clips and lists the two parent clip IDs.

---

## Errors

Errors use standard HTTP status codes with `{"error": "<message>"}` bodies.

| Status | Common causes |
| :---- | :---- |
| 400 | Missing both `lyrics` and `description`; using `style` with `description`; disallowed `voice_id`; missing `additional_audio_id` on a mashup |
| 401 | Missing or invalid `Authorization` header |
| 403 | Your plan does not include the requested feature (e.g. `generate.cover`, `generate.mashup`) |
| 404 | Source clip not found or not owned by your account (cover, mashup) |
| 429 | Rate limit (10 req/s sustained, 20 burst) or plan quota exceeded |
| 500 | Server error — safe to retry after a short backoff |

---

## Limits & quotas

- **Request rate**: 10 requests/second sustained, 20-request burst, applied per IP.

---

## Account usage — `GET /v0/account/usage`

```shell
curl https://api.suno.com/v0/account/usage \
  -H "Authorization: Bearer sk_live_<your-key>"
```

Returns counters for each feature the plan gates, with the window they apply over.

[image1]: <data:image/png;base64,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>