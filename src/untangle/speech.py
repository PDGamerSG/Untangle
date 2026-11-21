"""Listen to an answer or briefing in an Indian language: translate the English text with Sarvam's translation
model, then read it aloud with its text-to-speech model.

Untangle's answers cite their sources inline (`[dec:...]`, `[pr:...]`). Those markers and Markdown punctuation are
removed before speaking; code identifiers stay in English because translation uses the code-mixed mode. The audio is
returned to the browser and never stored."""

from __future__ import annotations

import base64
import re
from typing import Any

from pydantic import BaseModel, Field

from untangle.config import settings
from untangle.kt.sarvam import TTS_MAX_CHARS, SarvamClient, SarvamError

LANGUAGES: dict[str, str] = {
    "en-IN": "English", "hi-IN": "हिन्दी (Hindi)", "bn-IN": "বাংলা (Bengali)", "ta-IN": "தமிழ் (Tamil)",
    "te-IN": "తెలుగు (Telugu)", "kn-IN": "ಕನ್ನಡ (Kannada)", "ml-IN": "മലയാളം (Malayalam)", "mr-IN": "मराठी (Marathi)",
    "gu-IN": "ગુજરાતી (Gujarati)", "pa-IN": "ਪੰਜਾਬੀ (Punjabi)", "od-IN": "ଓଡ଼ିଆ (Odia)",
}
MAX_TEXT = 2400

_CITATION = re.compile(r"\s*\[(?:dec|pr|issue|commit|comment|doc|utt|mtg|person|file|module|sym|cfg|dep|chunk|repo)[^\]]*\]")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    language: str = Field(default="hi-IN", max_length=10)


class SpeakResponse(BaseModel):
    language: str
    text: str
    audio_base64: str
    mime: str = "audio/mpeg"


def speakable(text: str) -> str:
    """Answer text without citation markers, links, Markdown emphasis or code ticks, cut at a sentence end."""
    value = _CITATION.sub("", text)
    value = _LINK.sub(r"\1", value)
    value = re.sub(r"[`*_#>|]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= MAX_TEXT:
        return value
    cut = value[:MAX_TEXT]
    end = max(cut.rfind(". "), cut.rfind("। "), cut.rfind("? "))
    return cut[: end + 1] if end > MAX_TEXT // 2 else cut


def speak(text: str, language: str, *, client: SarvamClient | None = None) -> SpeakResponse:
    if language not in LANGUAGES:
        raise ValueError(f"Choose one of: {', '.join(LANGUAGES)}.")
    clean = speakable(text)
    if not clean:
        raise ValueError("There is no text to read aloud.")
    s = settings()
    own = client is None
    if client is None:
        if not s.sarvam_api_key:
            raise SarvamError("SARVAM_API_KEY is not set")
        client = SarvamClient(s.sarvam_api_key, timeout=30.0, retries=1)
    try:
        spoken = clean if language == "en-IN" else client.translate(clean, source="en-IN", target=language, mode="code-mixed")
        limit = TTS_MAX_CHARS.get(s.sarvam_tts_model, 1500)
        audio = client.text_to_speech(spoken[:limit], language=language, model=s.sarvam_tts_model, speaker=s.sarvam_tts_speaker)
    finally:
        if own:
            client.close()
    return SpeakResponse(language=language, text=spoken, audio_base64=base64.b64encode(audio).decode("ascii"))


def languages() -> list[dict[str, Any]]:
    return [{"code": code, "name": name} for code, name in LANGUAGES.items()]


__all__ = ["LANGUAGES", "SpeakRequest", "SpeakResponse", "languages", "speak", "speakable"]
