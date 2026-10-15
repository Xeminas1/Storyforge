"""Optional local Kokoro neural TTS adapter. Zero runtime Python dependencies.

Only speaks to a fixed localhost service. No arbitrary URLs or remote services.
"""
import json
from engine import speech_friendly_prose
import os
import re
import urllib.error
import urllib.request

TTS_BASE = "http://127.0.0.1:7860"
MAX_TEXT = 1400
MAX_AUDIO = 7 * 1024 * 1024
VOICE = re.compile(r"^[a-z]{2}_[a-z0-9_]{2,35}$")
KNOWN_VOICES = ["bm_george", "bm_lewis", "bf_emma", "bf_isabella", "am_michael", "am_adam", "af_heart", "af_bella"]


def status():
    try:
        with urllib.request.urlopen(TTS_BASE + "/health", timeout=1.5) as res:
            if res.status != 200:
                raise ValueError("Speech server unavailable")
        return {"available": True, "engine": "KokoroTTS", "voices": KNOWN_VOICES}
    except (OSError, ValueError, TimeoutError, urllib.error.URLError):
        return {"available": False, "engine": "KokoroTTS", "voices": KNOWN_VOICES}


def synthesize(payload: dict) -> bytes:
    text = speech_friendly_prose(str(payload.get("text", ""))).strip()
    if not text or len(text) > MAX_TEXT:
        raise ValueError(f"Narration segment must contain 1–{MAX_TEXT} characters")
    voice = str(payload.get("voice") or "bm_george")
    if not VOICE.fullmatch(voice):
        raise ValueError("Invalid neural voice")
    try:
        speed = float(payload.get("speed", 1))
    except (TypeError, ValueError):
        raise ValueError("Invalid speech speed") from None
    if not (0.7 <= speed <= 1.4):
        raise ValueError("Speech speed must be between 0.7 and 1.4")
    data = json.dumps({"model": "kokoro", "voice": voice, "input": text,
                       "response_format": "mp3", "speed": speed}).encode("utf-8")
    req = urllib.request.Request(TTS_BASE + "/v1/audio/speech", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=95) as res:
            kind = res.headers.get("Content-Type", "").lower()
            if kind and not (kind.startswith("audio/") or kind.startswith("application/octet-stream")):
                raise RuntimeError("Kokoro returned an unexpected audio format")
            audio = res.read(MAX_AUDIO + 1)
            if len(audio) > MAX_AUDIO:
                raise RuntimeError("Narration audio was too large")
            if not audio:
                raise RuntimeError("Kokoro generated no audio")
            return audio
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Kokoro rejected voice synthesis (HTTP {exc.code}); check the voice selection and Kokoro logs") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("KokoroTTS is offline. Start the local voice server or select browser voice") from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError("KokoroTTS timed out or stopped responding") from exc
