"""
PMIR-Net-Lite: Confirmation Dialogue & Verification Gate Module.
Enforces the mandatory Confirm / Edit / Reject workflow.
No prediction is ever auto-spoken or added to the personal dictionary without explicit confirmation.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pmir.matcher import MatchResult, IntentMatcher
from pmir.personal_dictionary import PersonalDictionary
from pmir.tts import TTSProvider, ConsoleTTSProvider


class DialogueAction(str, Enum):
    CONFIRM = "CONFIRM"
    EDIT = "EDIT"
    REJECT = "REJECT"
    CLARIFY = "CLARIFY"
    QUIT = "QUIT"


class ConfirmationGate:
    """
    Manages interactive user verification and enforces safety boundaries.
    """

    def __init__(
        self,
        matcher: IntentMatcher,
        personal_dict: PersonalDictionary,
        tts: Optional[TTSProvider] = None
    ):
        self.matcher = matcher
        self.personal_dict = personal_dict
        self.tts = tts or ConsoleTTSProvider()

    def process_turn(
        self,
        raw_input: str,
        user_action: Optional[DialogueAction] = None,
        corrected_intent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Non-interactive / programmatic single turn processing.
        Useful for batch evaluation and unit tests.
        """
        match_res = self.matcher.match(raw_input)

        if user_action is None:
            # Default behavior if not pre-specified
            user_action = DialogueAction.CONFIRM if not match_res.is_abstain else DialogueAction.CLARIFY

        result_payload = {
            "raw_input": raw_input,
            "match_result": match_res,
            "action_taken": user_action,
            "dictionary_updated": False,
            "tts_spoken": False,
            "final_intent_id": None,
            "final_tts_text": None,
        }

        if user_action == DialogueAction.CONFIRM:
            target_intent = match_res.intent_id
            target_tts = match_res.tts_response
            urgency = match_res.urgency

            # Update personal dictionary
            self.personal_dict.add_entry(raw_input, target_intent, note="Confirmed by user")
            # Speak TTS
            self.tts.speak(target_tts, intent_id=target_intent, urgency=urgency)

            result_payload.update({
                "dictionary_updated": True,
                "tts_spoken": True,
                "final_intent_id": target_intent,
                "final_tts_text": target_tts
            })

        elif user_action == DialogueAction.EDIT:
            if not corrected_intent_id or corrected_intent_id not in self.matcher.intents:
                # If invalid correction provided, fallback to reject
                result_payload["action_taken"] = DialogueAction.REJECT
                return result_payload

            intent_meta = self.matcher.intents[corrected_intent_id]
            target_tts = intent_meta.get("tts_response", "Request acknowledged.")
            urgency = intent_meta.get("urgency", "medium")

            # Update personal dictionary with the CORRECTION
            self.personal_dict.add_entry(raw_input, corrected_intent_id, note="Corrected via user edit")
            # Speak TTS
            self.tts.speak(target_tts, intent_id=corrected_intent_id, urgency=urgency)

            result_payload.update({
                "dictionary_updated": True,
                "tts_spoken": True,
                "final_intent_id": corrected_intent_id,
                "final_tts_text": target_tts
            })

        elif user_action == DialogueAction.REJECT:
            # Explicitly do NOT update dictionary and do NOT speak TTS
            result_payload.update({
                "dictionary_updated": False,
                "tts_spoken": False,
                "final_intent_id": None,
                "final_tts_text": None
            })

        return result_payload

    def interactive_turn(self, raw_input: str) -> Optional[Dict[str, Any]]:
        """
        Runs an interactive CLI turn prompting the user for Confirm/Edit/Reject.
        """
        print(f"\n" + "-" * 55)
        print(f"[INPUT] Raw Input: \"{raw_input}\"")

        match_res = self.matcher.match(raw_input)

        print(f"[PREDICTION] Intent  : [{match_res.intent_id}] - {match_res.canonical_label}")
        print(f"[CONFIDENCE] Score   : {match_res.confidence:.1%} (Personalized Match: {match_res.is_personal})")
        print(f"[PROPOSED]   Speech  : \"{match_res.tts_response}\"")

        if match_res.is_abstain:
            print(f"[ABSTENTION TRIGGERED]: {match_res.clarification_prompt}")
            if match_res.top_alternatives:
                print("   Alternative candidates:")
                for idx, alt in enumerate(match_res.top_alternatives, start=1):
                    print(f"   [{idx}] {alt['intent_id']} ({alt['canonical_label']}) - Conf: {alt['confidence']:.1%}")

        print("-" * 55)
        print("Choose an action:")
        print("  [C] Confirm prediction & Speak")
        print("  [E] Edit / Select different intent")
        print("  [R] Reject prediction")
        print("  [Q] Quit session")

        while True:
            choice = input("Your Choice (C/E/R/Q): ").strip().upper()
            if choice in ("C", "CONFIRM"):
                return self.process_turn(raw_input, user_action=DialogueAction.CONFIRM)

            elif choice in ("E", "EDIT"):
                print("\nAvailable Intents:")
                intent_list = list(self.matcher.intents.keys())
                for i, iid in enumerate(intent_list, 1):
                    label = self.matcher.intents[iid].get("canonical_label", "")
                    print(f"  {i:2d}. [{iid}] {label}")

                sel = input("\nEnter Intent Number or exact ID: ").strip()
                selected_id = None
                if sel.isdigit() and 1 <= int(sel) <= len(intent_list):
                    selected_id = intent_list[int(sel) - 1]
                elif sel.upper() in self.matcher.intents:
                    selected_id = sel.upper()

                if selected_id:
                    return self.process_turn(
                        raw_input,
                        user_action=DialogueAction.EDIT,
                        corrected_intent_id=selected_id
                    )
                else:
                    print("[!] Invalid selection. Please try again.")

            elif choice in ("R", "REJECT"):
                print("[X] Prediction rejected. Personal dictionary was NOT modified.")
                return self.process_turn(raw_input, user_action=DialogueAction.REJECT)

            elif choice in ("Q", "QUIT"):
                print("Exiting dialogue session.")
                return None
            else:
                print("Invalid input. Please enter C, E, R, or Q.")
