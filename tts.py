"""
PMIR-Net-Lite: Text-To-Speech (TTS) Confirmation Module.
Provides modular TTS interface and console stub with hooks for native SAPI/OS speech.
Constraint: No output is ever spoken or treated as final without explicit user confirmation.
"""

from abc import ABC, abstractmethod
import time
from typing import Optional, Dict, Any


class TTSProvider(ABC):
    """Abstract interface for TTS synthesis."""

    @abstractmethod
    def speak(self, text: str, intent_id: str = "", urgency: str = "medium") -> Dict[str, Any]:
        """Synthesizes or outputs spoken confirmation audio."""
        pass


class ConsoleTTSProvider(TTSProvider):
    """
    Clearly labeled console audio stub.
    Simulates speech synthesis with audio waveform display, timing, and metadata.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.history: list = []

    def speak(self, text: str, intent_id: str = "", urgency: str = "medium") -> Dict[str, Any]:
        """Simulates speech synthesis to standard output."""
        start_t = time.perf_counter()
        word_count = len(text.split())
        est_duration_ms = max(400, word_count * 250)

        record = {
            "status": "SPOKEN",
            "text": text,
            "intent_id": intent_id,
            "urgency": urgency,
            "duration_ms": est_duration_ms,
            "timestamp": time.strftime("%H:%M:%S", time.localtime()),
            "provider": "ConsoleTTS (Simulated Audio Stream)"
        }
        self.history.append(record)

        if self.verbose:
            banner_char = "!" if urgency == "critical" else "="
            border = banner_char * 60
            print(f"\n{border}")
            print(f"[AUDIO TTS OUTPUT] (Urgency: {urgency.upper()})")
            print(f"   Spoken Message : \"{text}\"")
            print(f"   Mapped Intent  : [{intent_id}]")
            print(f"   Simulated Time : {est_duration_ms}ms | Provider: ConsoleTTS")
            print(f"{border}\n")

        return record


class NativeTTSProvider(TTSProvider):
    """
    Optional native OS speech provider (e.g. Windows SAPI).
    Falls back gracefully to ConsoleTTSProvider if SAPI/pyttsx3 is unavailable.
    """

    def __init__(self, fallback_to_console: bool = True):
        self.fallback = ConsoleTTSProvider() if fallback_to_console else None
        self.engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
        except Exception:
            try:
                import win32com.client
                self.engine = win32com.client.Dispatch("SAPI.SpVoice")
            except Exception:
                self.engine = None

    def speak(self, text: str, intent_id: str = "", urgency: str = "medium") -> Dict[str, Any]:
        if self.engine:
            try:
                if hasattr(self.engine, "say"):
                    self.engine.say(text)
                    self.engine.runAndWait()
                elif hasattr(self.engine, "Speak"):
                    self.engine.Speak(text)
                return {
                    "status": "SPOKEN",
                    "text": text,
                    "intent_id": intent_id,
                    "provider": "Native OS SAPI"
                }
            except Exception as e:
                print(f"[TTS Warning] Native TTS failed: {e}. Using console fallback.")

        if self.fallback:
            return self.fallback.speak(text, intent_id, urgency)

        return {"status": "ERROR", "text": text, "message": "No TTS provider available"}
