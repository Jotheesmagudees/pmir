"""
PMIR-Net-Lite: Personalized Intent Mapping for Imperfect Speech/Transcripts
Assistive NLP prototype for robust, transparent, human-in-the-loop intent mapping.
"""

__version__ = "0.1.0"
__author__ = "PMIR Engineering Team"

from pmir.normalizer import TextNormalizer
from pmir.matcher import IntentMatcher, MatchResult
from pmir.personal_dictionary import PersonalDictionary
from pmir.dialogue import ConfirmationGate, DialogueAction
from pmir.tts import TTSProvider, ConsoleTTSProvider
from pmir.pipeline import PMIRPipeline

__all__ = [
    "TextNormalizer",
    "IntentMatcher",
    "MatchResult",
    "PersonalDictionary",
    "ConfirmationGate",
    "DialogueAction",
    "TTSProvider",
    "ConsoleTTSProvider",
    "PMIRPipeline",
]

