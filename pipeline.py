"""
PMIR-Net-Lite: Core Pipeline Orchestrator.
Unifies Text Normalization, Multi-Signal Matching, Personal Dictionary,
Confirmation Gate, and TTS Output into a cohesive, modular architecture.
"""

import os
from typing import Optional, Dict, Any, List
from pmir.normalizer import TextNormalizer
from pmir.personal_dictionary import PersonalDictionary
from pmir.matcher import IntentMatcher, MatchResult
from pmir.dialogue import ConfirmationGate, DialogueAction
from pmir.tts import TTSProvider, ConsoleTTSProvider


class PMIRPipeline:
    """
    Main entry point for PMIR-Net-Lite.
    Provides complete end-to-end processing with modular swap capability.
    """

    def __init__(
        self,
        intents_path: Optional[str] = None,
        personal_dict_path: Optional[str] = None,
        abstention_threshold: float = 0.52,
        personal_boost: float = 0.12,
        tts_provider: Optional[TTSProvider] = None,
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_intents = os.path.join(base_dir, "data", "intents.json")
        default_dict = os.path.join(base_dir, "data", "personal_dict.json")

        self.intents_path = intents_path or default_intents
        self.personal_dict_path = personal_dict_path or default_dict

        self.normalizer = TextNormalizer()
        self.personal_dict = PersonalDictionary(filepath=self.personal_dict_path)
        self.matcher = IntentMatcher(
            intents_path=self.intents_path,
            personal_dict=self.personal_dict,
            abstention_threshold=abstention_threshold,
            personal_boost=personal_boost
        )
        self.tts = tts_provider or ConsoleTTSProvider()
        self.gate = ConfirmationGate(
            matcher=self.matcher,
            personal_dict=self.personal_dict,
            tts=self.tts
        )

    def predict(self, raw_transcript: str) -> MatchResult:
        """Runs normalization and matcher to produce candidate prediction."""
        return self.matcher.match(raw_transcript)

    def process(
        self,
        raw_transcript: str,
        action: Optional[DialogueAction] = None,
        corrected_intent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs end-to-end turn with verification gating."""
        return self.gate.process_turn(
            raw_input=raw_transcript,
            user_action=action,
            corrected_intent_id=corrected_intent_id
        )

    def interactive_turn(self, raw_transcript: str) -> Optional[Dict[str, Any]]:
        """Prompts user interactively for Confirm/Edit/Reject."""
        return self.gate.interactive_turn(raw_transcript)

    def list_personal_dictionary(self) -> List[Dict[str, Any]]:
        """Returns inspectable personal dictionary mappings."""
        return self.personal_dict.list_entries()

    def clear_personal_dictionary(self) -> None:
        """Clears personalized memory."""
        self.personal_dict.clear()

