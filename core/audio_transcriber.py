"""
audio_transcriber.py
Live audio capture from an input device and transcription with faster-whisper.
"""

import queue
import re
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class LiveAudioTranscriber:
    @staticmethod
    def list_input_devices() -> list[str]:
        devices = sd.query_devices()
        names = []
        for dev in devices:
            if dev.get("max_input_channels", 0) > 0:
                name = str(dev.get("name", "")).strip()
                if name:
                    names.append(name)

        # Keep unique names preserving order.
        unique = list(dict.fromkeys(names))
        unique.sort(key=lambda n: (0 if "cable output" in n.lower() else 1, n.lower()))
        return unique

    def __init__(
        self,
        model_size: str = "small",
        language: str = "es",
        sample_rate: int = 16000,
        chunk_seconds: int = 6,
        min_phrase_chars: int = 8,
    ):
        self.model_size = model_size
        self.language = language
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.min_phrase_chars = min_phrase_chars

        self._model: Optional[WhisperModel] = None
        self._stream = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=120)
        self._pending_text = ""
        self._last_emitted = ""

    @staticmethod
    def find_input_device(device_hint: str) -> int:
        hint = (device_hint or "").lower()
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name = str(dev.get("name", ""))
            max_in = dev.get("max_input_channels", 0)
            if max_in > 0 and hint in name.lower():
                return i
        raise RuntimeError(
            f"No se encontro dispositivo de entrada con: '{device_hint}'. "
            "En VB-Cable normalmente es 'CABLE Output'."
        )

    def start(
        self,
        device_hint: str,
        on_text: Callable[[str], None],
        on_log: Callable[[str], None],
    ):
        if self._running:
            return

        device_index = self.find_input_device(device_hint)

        if self._model is None or self.model_size != getattr(self, "_loaded_model_size", ""):
            on_log(f"Cargando Whisper '{self.model_size}'...")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self._loaded_model_size = self.model_size

        self._running = True

        def _audio_callback(indata, frames, time_info, status):
            if status:
                on_log(f"Audio status: {status}")
            if not self._running:
                return
            try:
                self._audio_q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                # Drop oldest audio to keep real-time behavior.
                try:
                    self._audio_q.get_nowait()
                    self._audio_q.put_nowait(indata[:, 0].copy())
                except Exception:
                    pass

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=device_index,
            callback=_audio_callback,
        )
        self._stream.start()

        self._thread = threading.Thread(
            target=self._run_loop,
            args=(on_text, on_log),
            daemon=True,
        )
        self._thread.start()

        device_name = sd.query_devices(device_index).get("name", str(device_index))
        on_log(f"Transcripcion activa en: {device_name}")

    def stop(self):
        if not self._running:
            return
        self._running = False

        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None

        # Empty queue after stop.
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except Exception:
                break

        self._pending_text = ""

    def _run_loop(self, on_text: Callable[[str], None], on_log: Callable[[str], None]):
        chunk_samples = self.sample_rate * self.chunk_seconds
        audio_parts = []
        total = 0

        while self._running:
            try:
                part = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            audio_parts.append(part)
            total += len(part)

            if total < chunk_samples:
                continue

            audio = np.concatenate(audio_parts, axis=0)
            current = audio[:chunk_samples]
            rest = audio[chunk_samples:]

            audio_parts = [rest] if len(rest) else []
            total = len(rest)

            try:
                segments, _ = self._model.transcribe(
                    current,
                    language=self.language,
                    beam_size=1,
                    vad_filter=True,
                    no_speech_threshold=0.7,
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
                self._consume_text(text, on_text)
            except Exception as e:
                on_log(f"Error transcribiendo audio: {e}")

    def _consume_text(self, text: str, on_text: Callable[[str], None]):
        if not text:
            return

        cleaned = " ".join(text.split()).strip()
        if len(cleaned) < self.min_phrase_chars and not any(p in cleaned for p in ".?!"):
            return

        self._pending_text = f"{self._pending_text} {cleaned}".strip()

        parts = re.split(r"([.!?]+)", self._pending_text)
        if len(parts) < 3:
            if len(self._pending_text) > 220:
                self._emit(self._pending_text, on_text)
                self._pending_text = ""
            return

        rebuilt = ""
        for i in range(0, len(parts) - 1, 2):
            fragment = (parts[i] + parts[i + 1]).strip()
            if fragment:
                self._emit(fragment, on_text)
            rebuilt = " ".join(parts[i + 2:]).strip()
        self._pending_text = rebuilt

    def _emit(self, phrase: str, on_text: Callable[[str], None]):
        output = " ".join(phrase.split()).strip()
        if len(output) < self.min_phrase_chars:
            return
        if output == self._last_emitted:
            return
        self._last_emitted = output
        on_text(output)
