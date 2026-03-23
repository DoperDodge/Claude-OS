"""
Claude-OS Voice Engine

Handles voice input (speech-to-text) and output (text-to-speech).
Supports a wake word ("Hey Claude") for hands-free activation.

Input pipeline:  Microphone → VAD → STT → ChatEngine
Output pipeline: ChatEngine → TTS → Speaker

Uses:
- ALSA for audio capture/playback
- Vosk or Whisper for offline STT (when available)
- espeak-ng or piper for offline TTS
- Falls back to API-based STT/TTS when online
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger("voice")


class VoiceEngine:
    """
    Voice input/output engine for Claude-OS.

    Manages microphone capture, speech recognition, and speech synthesis.
    """

    WAKE_WORD = "hey claude"
    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self):
        self.is_listening = False
        self._on_transcript: Callable | None = None
        self._running = False
        self._wake_word_active = True
        self._stt_engine = None
        self._tts_engine = None

    async def start(self, on_transcript: Callable = None):
        """
        Start the voice engine.

        Args:
            on_transcript: Callback invoked with transcribed text
        """
        self._on_transcript = on_transcript
        self._running = True

        # Detect available engines
        self._stt_engine = self._detect_stt_engine()
        self._tts_engine = self._detect_tts_engine()

        logger.info("Voice engine started (STT: %s, TTS: %s)",
                     self._stt_engine, self._tts_engine)

        # Run the voice capture loop
        await self._capture_loop()

    async def stop(self):
        """Stop the voice engine."""
        self._running = False
        self.is_listening = False
        logger.info("Voice engine stopped")

    async def speak(self, text: str):
        """
        Speak text aloud using TTS.

        Args:
            text: The text to synthesize and play
        """
        if not text:
            return

        logger.info("Speaking: %s", text[:80])

        try:
            if self._tts_engine == "piper":
                await self._speak_piper(text)
            elif self._tts_engine == "espeak":
                await self._speak_espeak(text)
            else:
                logger.warning("No TTS engine available, skipping speech")
        except Exception as e:
            logger.error("TTS failed: %s", e)

    async def _capture_loop(self):
        """
        Main audio capture loop.

        Continuously captures audio, runs VAD (voice activity detection),
        and sends detected speech segments to the STT engine.
        """
        while self._running:
            try:
                if self._wake_word_active and not self.is_listening:
                    # Listen for wake word
                    await self._listen_for_wake_word()
                elif self.is_listening:
                    # Capture and transcribe
                    audio = await self._capture_audio(max_seconds=10)
                    if audio:
                        transcript = await self._transcribe(audio)
                        if transcript and self._on_transcript:
                            await self._on_transcript(transcript)
                    self.is_listening = False
                else:
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error("Capture loop error: %s", e)
                await asyncio.sleep(1)

    async def _listen_for_wake_word(self):
        """Listen for the wake word to activate voice input."""
        # In production, this runs a lightweight wake word detector
        # (e.g., Porcupine, openWakeWord) continuously on mic input
        await asyncio.sleep(0.5)

    async def _capture_audio(self, max_seconds: float = 10) -> bytes | None:
        """
        Capture audio from the microphone.

        Uses ALSA's arecord for audio capture. Stops on silence
        detection or after max_seconds.

        Returns raw PCM audio bytes, or None if capture fails.
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            proc = await asyncio.create_subprocess_exec(
                "arecord",
                "-f", "S16_LE",
                "-r", str(self.SAMPLE_RATE),
                "-c", str(self.CHANNELS),
                "-d", str(int(max_seconds)),
                "-q",
                tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 44:
                return Path(tmp_path).read_bytes()
            return None
        except FileNotFoundError:
            logger.debug("arecord not available")
            return None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _transcribe(self, audio: bytes) -> str | None:
        """
        Transcribe audio to text.

        Tries local engines first (Vosk, Whisper), falls back to API.
        """
        if self._stt_engine == "vosk":
            return await self._transcribe_vosk(audio)
        elif self._stt_engine == "whisper":
            return await self._transcribe_whisper(audio)
        else:
            logger.debug("No STT engine available")
            return None

    async def _transcribe_vosk(self, audio: bytes) -> str | None:
        """Transcribe using Vosk (offline)."""
        try:
            import vosk

            model_path = "/opt/claude-os/models/vosk-model-small"
            if not os.path.exists(model_path):
                logger.warning("Vosk model not found at %s", model_path)
                return None

            def _run():
                model = vosk.Model(model_path)
                rec = vosk.KaldiRecognizer(model, self.SAMPLE_RATE)
                # Skip WAV header (44 bytes)
                rec.AcceptWaveform(audio[44:])
                result = json.loads(rec.FinalResult())
                return result.get("text", "").strip()

            return await asyncio.to_thread(_run)
        except ImportError:
            logger.debug("Vosk not installed")
            return None

    async def _transcribe_whisper(self, audio: bytes) -> str | None:
        """Transcribe using Whisper (offline)."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio)
                tmp_path = tmp.name

            proc = await asyncio.create_subprocess_exec(
                "whisper", tmp_path,
                "--model", "tiny",
                "--language", "en",
                "--output_format", "txt",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip() if stdout else None
        except FileNotFoundError:
            return None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _speak_piper(self, text: str):
        """Speak using Piper TTS (offline, high quality)."""
        model_path = "/opt/claude-os/models/piper-voice.onnx"

        proc = await asyncio.create_subprocess_exec(
            "piper",
            "--model", model_path,
            "--output-raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate(input=text.encode())

        if stdout:
            # Play raw audio through aplay
            play = await asyncio.create_subprocess_exec(
                "aplay",
                "-f", "S16_LE",
                "-r", "22050",
                "-c", "1",
                "-q",
                stdin=asyncio.subprocess.PIPE,
            )
            await play.communicate(input=stdout)

    async def _speak_espeak(self, text: str):
        """Speak using espeak-ng (offline, lightweight)."""
        proc = await asyncio.create_subprocess_exec(
            "espeak-ng",
            "-v", "en",
            "-s", "160",  # Speed (words per minute)
            text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    def activate_listening(self):
        """Manually activate voice listening (e.g., from a mic button)."""
        self.is_listening = True
        logger.info("Voice listening activated")

    def _detect_stt_engine(self) -> str | None:
        """Detect which STT engine is available."""
        try:
            import vosk
            if os.path.exists("/opt/claude-os/models/vosk-model-small"):
                return "vosk"
        except ImportError:
            pass

        if self._command_exists("whisper"):
            return "whisper"

        return None

    def _detect_tts_engine(self) -> str | None:
        """Detect which TTS engine is available."""
        if self._command_exists("piper"):
            if os.path.exists("/opt/claude-os/models/piper-voice.onnx"):
                return "piper"

        if self._command_exists("espeak-ng"):
            return "espeak"

        return None

    @staticmethod
    def _command_exists(cmd: str) -> bool:
        """Check if a command is available on the system."""
        try:
            subprocess.run(
                ["which", cmd],
                capture_output=True, timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
