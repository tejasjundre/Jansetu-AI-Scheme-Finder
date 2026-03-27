import io
import tempfile
from pathlib import Path

import speech_recognition as sr
from gtts import gTTS


LANG_LOCALES = {
    "en": "en-IN",
    "hi": "hi-IN",
    "mr": "mr-IN",
}

GTTS_LANG = {
    "en": "en",
    "hi": "hi",
    "mr": "mr",
}


def locale_for_lang(lang: str) -> str:
    return LANG_LOCALES.get(str(lang or "").strip().lower(), "en-IN")


def _transcribe_wav_file(file_path: Path, locale: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(str(file_path)) as source:
        audio = recognizer.record(source)
    return recognizer.recognize_google(audio, language=locale)


def transcribe_audio_upload(uploaded_file, lang: str = "en") -> str:
    locale = locale_for_lang(lang)
    suffix = Path(getattr(uploaded_file, "name", "")).suffix or ".wav"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        input_path = temp_dir_path / f"voice_input{suffix}"
        with input_path.open("wb") as handle:
            for chunk in uploaded_file.chunks():
                handle.write(chunk)

        try:
            return _transcribe_wav_file(input_path, locale)
        except Exception:
            pass

        # Fallback conversion for browsers that send webm/ogg/mp4 containers.
        converted_path = temp_dir_path / "voice_input.wav"
        try:
            from pydub import AudioSegment

            audio_segment = AudioSegment.from_file(str(input_path))
            audio_segment.export(str(converted_path), format="wav")
            return _transcribe_wav_file(converted_path, locale)
        except Exception as exc:
            raise RuntimeError("Unable to decode audio input for transcription.") from exc


def synthesize_speech_mp3(text: str, lang: str = "en") -> bytes:
    cleaned = str(text or "").strip()
    if not cleaned:
        return b""
    language = GTTS_LANG.get(str(lang or "").strip().lower(), "en")
    tts = gTTS(text=cleaned, lang=language, tld="co.in")
    stream = io.BytesIO()
    tts.write_to_fp(stream)
    return stream.getvalue()
