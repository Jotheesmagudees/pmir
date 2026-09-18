"""
PMIR-Net-Lite: Multi-Signal Fuzzy & Phonetic Intent Matcher.
Combines Levenshtein distance, token alignment, character n-gram Jaccard,
content-word weighting, and phonetic Metaphone/Soundex codes with confidence scoring and abstention.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from pmir.normalizer import TextNormalizer
from pmir.personal_dictionary import PersonalDictionary


@dataclass
class MatchResult:
    """Encapsulates the intent prediction result, confidence, and explanation."""
    intent_id: str
    canonical_label: str
    confidence: float
    matched_phrase: str
    is_personal: bool
    is_abstain: bool
    tts_response: str
    urgency: str = "medium"
    top_alternatives: List[Dict[str, Any]] = field(default_factory=list)
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    clarification_prompt: str = ""


class IntentMatcher:
    """
    Robust multi-signal intent matcher.
    Evaluates inputs against personalized phrase entries and base intent templates.
    """

    # Functional / grammatical stop words that carry lower semantic intent specificity
    STOP_WORDS: Set[str] = {
        "i", "me", "my", "myself", "you", "your", "can", "could", "would", "will", "shall",
        "please", "have", "some", "want", "need", "a", "an", "the", "it", "is", "am", "are",
        "to", "for", "in", "of", "on", "at", "give", "bring", "get", "do", "does", "did",
        "with", "and", "or", "so", "that", "this", "be", "here", "there"
    }

    def __init__(
        self,
        intents_path: Optional[str] = None,
        personal_dict: Optional[PersonalDictionary] = None,
        abstention_threshold: float = 0.52,
        personal_boost: float = 0.15,
    ):
        self.normalizer = TextNormalizer()
        self.personal_dict = personal_dict or PersonalDictionary()
        self.abstention_threshold = abstention_threshold
        self.personal_boost = personal_boost
        self.intents: Dict[str, Dict[str, Any]] = {}
        self.intents_path = intents_path

        if intents_path:
            self.load_intents(intents_path)

    def load_intents(self, filepath: str) -> None:
        """Loads canonical intents definition from JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            for intent in data.get("intents", []):
                self.intents[intent["id"]] = intent

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Pure-Python dynamic programming Levenshtein distance."""
        if s1 == s2:
            return 0
        if len(s1) == 0:
            return len(s2)
        if len(s2) == 0:
            return len(s1)

        v0 = list(range(len(s2) + 1))
        v1 = [0] * (len(s2) + 1)

        for i in range(len(s1)):
            v1[0] = i + 1
            for j in range(len(s2)):
                cost = 0 if s1[i] == s2[j] else 1
                v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
            v0, v1 = v1, [0] * (len(s2) + 1)

        return v0[len(s2)]

    @classmethod
    def levenshtein_ratio(cls, s1: str, s2: str) -> float:
        """Calculates normalized Levenshtein similarity ratio between 0.0 and 1.0."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        dist = cls.levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return max(0.0, 1.0 - (dist / max_len))

    @staticmethod
    def jaccard_similarity(tokens1: List[str], tokens2: List[str]) -> float:
        """Computes Jaccard set similarity over token lists."""
        set1, set2 = set(tokens1), set(tokens2)
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union

    @staticmethod
    def get_character_ngrams(s: str, n: int = 3) -> List[str]:
        """Extracts character n-grams from a string."""
        s_clean = s.replace(" ", "")
        s_padded = f"#{s_clean}#"
        if len(s_padded) < n:
            return [s_padded]
        return [s_padded[i:i + n] for i in range(len(s_padded) - n + 1)]

    def character_ngram_similarity(self, s1: str, s2: str) -> float:
        """Computes Jaccard similarity over character 2-grams and 3-grams."""
        ng2_1 = self.get_character_ngrams(s1, 2)
        ng2_2 = self.get_character_ngrams(s2, 2)
        ng3_1 = self.get_character_ngrams(s1, 3)
        ng3_2 = self.get_character_ngrams(s2, 3)

        sim2 = self.jaccard_similarity(ng2_1, ng2_2)
        sim3 = self.jaccard_similarity(ng3_1, ng3_2)
        return (sim2 * 0.4) + (sim3 * 0.6)

    def token_word_similarity(self, w1: str, w2: str) -> float:
        """
        Computes composite similarity between two individual words using:
          - Levenshtein ratio
          - Metaphone equality
          - Soundex equality
        """
        if w1 == w2:
            return 1.0
        lev = self.levenshtein_ratio(w1, w2)
        meta_match = 1.0 if self.normalizer.metaphone(w1) == self.normalizer.metaphone(w2) and self.normalizer.metaphone(w1) != "" else 0.0
        sndx_match = 1.0 if self.normalizer.soundex(w1) == self.normalizer.soundex(w2) and self.normalizer.soundex(w1) != "0000" else 0.0

        phone = max(meta_match, sndx_match * 0.85)
        return max(lev, phone * 0.90, (lev * 0.6 + phone * 0.4))

    def weighted_token_alignment(self, query_tokens: List[str], cand_tokens: List[str]) -> Tuple[float, float]:
        """
        Computes weighted token alignment where content words are weighted higher than stop words.
        Returns: (query_coverage, candidate_coverage)
        """
        if not query_tokens or not cand_tokens:
            return 0.0, 0.0

        def get_weight(w: str) -> float:
            return 1.0 if w in self.STOP_WORDS else 2.5

        # Match query tokens against best candidate token
        q_weights = [get_weight(q) for q in query_tokens]
        q_scores = []
        for q in query_tokens:
            best_sim = max([self.token_word_similarity(q, c) for c in cand_tokens], default=0.0)
            q_scores.append(best_sim)

        weighted_q_sim = sum(s * w for s, w in zip(q_scores, q_weights)) / sum(q_weights)

        # Match candidate tokens against best query token
        c_weights = [get_weight(c) for c in cand_tokens]
        c_scores = []
        for c in cand_tokens:
            best_sim = max([self.token_word_similarity(c, q) for q in query_tokens], default=0.0)
            c_scores.append(best_sim)

        weighted_c_sim = sum(s * w for s, w in zip(c_scores, c_weights)) / sum(c_weights)

        return weighted_q_sim, weighted_c_sim

    def calculate_phrase_similarity(self, query: str, candidate_phrase: str) -> Tuple[float, Dict[str, float]]:
        """
        Computes robust multi-signal similarity score between query and candidate phrase.
        Integrates:
          1. Exact match (1.0)
          2. Weighted token alignment (accounting for content vs stop words)
          3. Whole string Levenshtein & character n-gram similarity
          4. Token sort ratio
        """
        if query == candidate_phrase:
            return 1.0, {"lev": 1.0, "token_align": 1.0, "ngram": 1.0, "raw": 1.0}

        q_tokens = query.split()
        c_tokens = candidate_phrase.split()

        # Weighted token alignments
        q_align, c_align = self.weighted_token_alignment(q_tokens, c_tokens)
        token_align_score = (q_align * 0.6) + (c_align * 0.4)

        # Token sort ratio
        sorted_q = " ".join(sorted(q_tokens))
        sorted_c = " ".join(sorted(c_tokens))
        token_sort_ratio = self.levenshtein_ratio(sorted_q, sorted_c)

        # Character N-gram and whole-string Levenshtein
        ngram_sim = self.character_ngram_similarity(query, candidate_phrase)
        whole_lev = self.levenshtein_ratio(query, candidate_phrase)

        # Multi-signal weighted composite
        composite = (
            token_align_score * 0.50 +
            token_sort_ratio * 0.20 +
            ngram_sim * 0.20 +
            whole_lev * 0.10
        )

        # Bonus for high content-word overlap
        q_content = [t for t in q_tokens if t not in self.STOP_WORDS]
        c_content = [t for t in c_tokens if t not in self.STOP_WORDS]
        if q_content and c_content:
            content_match_count = 0
            for qc in q_content:
                if any(self.token_word_similarity(qc, cc) > 0.80 for cc in c_content):
                    content_match_count += 1
            content_ratio = content_match_count / len(q_content)
            if content_ratio >= 1.0:
                composite = min(1.0, max(composite, 0.85 + 0.15 * token_align_score))

        # Check for exact substring containment
        if len(query) >= 3 and (query in candidate_phrase or candidate_phrase in query):
            composite = min(1.0, composite + 0.08)

        score_details = {
            "token_align": round(token_align_score, 3),
            "token_sort": round(token_sort_ratio, 3),
            "ngram": round(ngram_sim, 3),
            "lev": round(whole_lev, 3),
            "raw": round(composite, 3)
        }
        return composite, score_details

    def match(self, raw_input: str) -> MatchResult:
        """
        Matches raw user input against personal dictionary and base intents.
        Returns top MatchResult with abstention assessment and alternative candidates.
        """
        norm_query = self.normalizer.normalize(raw_input)

        if not norm_query:
            return MatchResult(
                intent_id="UNKNOWN",
                canonical_label="Empty / Unintelligible Input",
                confidence=0.0,
                matched_phrase="",
                is_personal=False,
                is_abstain=True,
                tts_response="I could not hear or understand the request.",
                clarification_prompt="Input was empty or unintelligible. Please try again."
            )

        candidate_scores: List[Dict[str, Any]] = []

        # 1. Check Personal Dictionary First (with high priority / personalization boost)
        for phrase_key, entry in self.personal_dict.entries.items():
            norm_target = self.normalizer.normalize(phrase_key)
            sim, details = self.calculate_phrase_similarity(norm_query, norm_target)
            adjusted_score = min(1.0, sim + self.personal_boost if sim > 0.35 else sim)
            intent_id = entry["intent_id"]
            intent_meta = self.intents.get(intent_id, {})

            candidate_scores.append({
                "intent_id": intent_id,
                "canonical_label": intent_meta.get("canonical_label", intent_id),
                "tts_response": intent_meta.get("tts_response", "Request acknowledged."),
                "urgency": intent_meta.get("urgency", "medium"),
                "score": adjusted_score,
                "matched_phrase": phrase_key,
                "is_personal": True,
                "details": details
            })

        # 2. Check Base Intent Library
        for intent_id, intent_data in self.intents.items():
            for base_phrase in intent_data.get("base_phrases", []):
                norm_target = self.normalizer.normalize(base_phrase)
                sim, details = self.calculate_phrase_similarity(norm_query, norm_target)

                candidate_scores.append({
                    "intent_id": intent_id,
                    "canonical_label": intent_data.get("canonical_label", intent_id),
                    "tts_response": intent_data.get("tts_response", "Request acknowledged."),
                    "urgency": intent_data.get("urgency", "medium"),
                    "score": sim,
                    "matched_phrase": base_phrase,
                    "is_personal": False,
                    "details": details
                })

        # Sort all candidates by score descending
        candidate_scores.sort(key=lambda x: x["score"], reverse=True)

        if not candidate_scores:
            return MatchResult(
                intent_id="UNKNOWN",
                canonical_label="No Intent Found",
                confidence=0.0,
                matched_phrase="",
                is_personal=False,
                is_abstain=True,
                tts_response="No matching intent could be found.",
                clarification_prompt="No matching intent found. Would you like to select from standard options?"
            )

        top = candidate_scores[0]
        confidence = round(top["score"], 4)

        # Deduplicate top alternatives across distinct intent IDs
        seen_intents = {top["intent_id"]}
        alternatives = []
        for cand in candidate_scores[1:]:
            if cand["intent_id"] not in seen_intents:
                seen_intents.add(cand["intent_id"])
                alternatives.append({
                    "intent_id": cand["intent_id"],
                    "canonical_label": cand["canonical_label"],
                    "confidence": round(cand["score"], 4),
                    "matched_phrase": cand["matched_phrase"],
                    "is_personal": cand["is_personal"]
                })
            if len(alternatives) >= 3:
                break

        # Abstention decision
        is_abstain = confidence < self.abstention_threshold
        clarification = ""
        if is_abstain:
            alt_labels = ", ".join([f"'{a['canonical_label']}'" for a in alternatives[:2]])
            clarification = (
                f"Confidence ({confidence:.2f}) is below safe threshold ({self.abstention_threshold:.2f}). "
                f"Did you mean {alt_labels}?" if alt_labels else "Low confidence fragment. Please clarify."
            )

        return MatchResult(
            intent_id=top["intent_id"],
            canonical_label=top["canonical_label"],
            confidence=confidence,
            matched_phrase=top["matched_phrase"],
            is_personal=top["is_personal"],
            is_abstain=is_abstain,
            tts_response=top["tts_response"],
            urgency=top["urgency"],
            top_alternatives=alternatives,
            score_breakdown=top["details"],
            clarification_prompt=clarification
        )

