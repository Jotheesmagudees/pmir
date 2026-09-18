"""
PMIR-Net-Lite: Unit and Integration Test Suite.
Tests normalization, fuzzy matching, phonetic similarity, personal dictionary safety,
confirmation gates, and personalization feedback loop.
"""

import os
import shutil
import tempfile
import unittest

from pmir.normalizer import TextNormalizer
from pmir.matcher import IntentMatcher
from pmir.personal_dictionary import PersonalDictionary
from pmir.dialogue import ConfirmationGate, DialogueAction
from pmir.tts import ConsoleTTSProvider
from pmir.pipeline import PMIRPipeline


class TestPMIRPipeline(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dict_path = os.path.join(self.test_dir, "test_personal_dict.json")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.intents_path = os.path.join(base_dir, "data", "intents.json")

        self.normalizer = TextNormalizer()
        self.personal_dict = PersonalDictionary(filepath=self.dict_path)
        self.tts = ConsoleTTSProvider(verbose=False)
        self.matcher = IntentMatcher(
            intents_path=self.intents_path,
            personal_dict=self.personal_dict,
            abstention_threshold=0.52
        )
        self.gate = ConfirmationGate(
            matcher=self.matcher,
            personal_dict=self.personal_dict,
            tts=self.tts
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_normalizer_stutter_and_contractions(self):
        """Tests that stutters, elongations, and slang are properly cleaned."""
        raw = "w-w-w...waaaater plz gimme"
        cleaned = self.normalizer.normalize(raw)
        self.assertEqual(cleaned, "water please give me")

        raw2 = "p-p-please h-help i-i-im f-freezing"
        cleaned2 = self.normalizer.normalize(raw2)
        self.assertEqual(cleaned2, "please help i am freezing")

    def test_phonetic_encoding(self):
        """Tests soundex and metaphone consistency."""
        snd = self.normalizer.soundex("water")
        meta = self.normalizer.metaphone("water")
        self.assertEqual(snd, "W360")
        self.assertTrue(len(meta) > 0)

        # "water" vs "wader" should have identical or very similar phonetic codes
        self.assertEqual(self.normalizer.soundex("water"), self.normalizer.soundex("wader"))

    def test_confident_clean_match(self):
        """Tests standard high confidence match on base intents."""
        res = self.matcher.match("i need some water please")
        self.assertEqual(res.intent_id, "NEED_WATER")
        self.assertFalse(res.is_abstain)
        self.assertGreater(res.confidence, 0.70)

    def test_distorted_fuzzy_match(self):
        """Tests matching on phonetically distorted transcript."""
        res = self.matcher.match("w-w-wader plz")
        self.assertEqual(res.intent_id, "NEED_WATER")
        self.assertFalse(res.is_abstain)

    def test_abstention_on_ambiguous_fragment(self):
        """Tests that low-confidence/garbled fragments trigger abstention."""
        res = self.matcher.match("kld zzz")
        self.assertTrue(res.is_abstain)
        self.assertLess(res.confidence, 0.52)
        self.assertTrue(len(res.clarification_prompt) > 0)

    def test_personal_dictionary_crud(self):
        """Tests personal dictionary addition, lookup, removal, and persistence."""
        self.personal_dict.add_entry("aqua glass", "NEED_WATER", note="custom phrase")
        entry = self.personal_dict.get_entry("aqua glass")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["intent_id"], "NEED_WATER")

        # Reload from disk to verify persistence
        new_dict = PersonalDictionary(filepath=self.dict_path)
        self.assertIsNotNone(new_dict.get_entry("aqua glass"))

        # Remove entry
        self.personal_dict.remove_entry("aqua glass")
        self.assertIsNone(self.personal_dict.get_entry("aqua glass"))

    def test_strict_safety_gate_reject_does_not_save(self):
        """Tests that REJECT never touches personal dictionary or fires TTS."""
        initial_count = len(self.personal_dict.entries)
        res = self.gate.process_turn("obscure sound fragment", user_action=DialogueAction.REJECT)

        self.assertFalse(res["dictionary_updated"])
        self.assertFalse(res["tts_spoken"])
        self.assertEqual(len(self.personal_dict.entries), initial_count)
        self.assertIsNone(self.personal_dict.get_entry("obscure sound fragment"))

    def test_confirmation_updates_dictionary_and_tts(self):
        """Tests that CONFIRM saves the pair and executes TTS."""
        raw = "gimme wtr"
        res = self.gate.process_turn(raw, user_action=DialogueAction.CONFIRM)

        self.assertTrue(res["dictionary_updated"])
        self.assertTrue(res["tts_spoken"])
        self.assertEqual(res["final_intent_id"], "NEED_WATER")
        self.assertIsNotNone(self.personal_dict.get_entry(raw))

    def test_edit_updates_dictionary_with_correction(self):
        """Tests that EDIT corrects misclassified intent and registers the correction."""
        raw = "unusual code word alpha"
        # Force edit to EMERGENCY_HELP
        res = self.gate.process_turn(
            raw,
            user_action=DialogueAction.EDIT,
            corrected_intent_id="EMERGENCY_HELP"
        )
        self.assertTrue(res["dictionary_updated"])
        self.assertEqual(res["final_intent_id"], "EMERGENCY_HELP")

        # Subsequent prediction on this phrase should now immediately resolve to EMERGENCY_HELP
        next_match = self.matcher.match(raw)
        self.assertEqual(next_match.intent_id, "EMERGENCY_HELP")
        self.assertTrue(next_match.is_personal)
        self.assertGreater(next_match.confidence, 0.90)


if __name__ == "__main__":
    unittest.main()

