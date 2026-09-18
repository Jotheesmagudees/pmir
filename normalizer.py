"""
PMIR-Net-Lite: Text Normalization and Phonetic Encoding Module.
Handles transcript cleaning, stutter collapsing, contraction expansion,
and pure-Python phonetic encoding (Soundex & Metaphone).
"""

import re
from functools import lru_cache
from typing import List, Tuple


class TextNormalizer:
    """Normalizes raw/imperfect speech transcripts and produces phonetic tokens."""

    # Common spoken shorthand, AAC abbreviations, and contraction map
    CONTRACTION_MAP = {
        "dont": "do not",
        "don't": "do not",
        "cant": "cannot",
        "can't": "cannot",
        "wont": "will not",
        "won't": "will not",
        "im": "i am",
        "i'm": "i am",
        "ive": "i have",
        "i've": "i have",
        "ill": "i will",
        "i'll": "i will",
        "youre": "you are",
        "you're": "you are",
        "theyre": "they are",
        "they're": "they are",
        "thats": "that is",
        "that's": "that is",
        "whats": "what is",
        "what's": "what is",
        "wanna": "want to",
        "gonna": "going to",
        "gotta": "got to",
        "gimme": "give me",
        "lemme": "let me",
        "plz": "please",
        "pls": "please",
        "thx": "thank you",
        "ty": "thank you",
        "doc": "doctor",
        "meds": "medicine",
        "pill": "medicine",
        "pills": "medicine",
        "wtr": "water",
        "watr": "water",
        "drnk": "drink",
        "bth": "bathroom",
        "bthrm": "bathroom",
        "br": "bathroom",
        "tv": "television",
        "ac": "air conditioner",
    }

    # Common filler words to de-emphasize
    FILLERS = {"uh", "um", "ah", "er", "eh", "like", "hmm", "huh"}

    def __init__(self, strip_fillers: bool = True):
        self.strip_fillers = strip_fillers

    def normalize(self, text: str) -> str:
        """
        Main pipeline for cleaning and standardizing transcript strings.
        Steps:
          1. Lowercase & strip
          2. Collapse hyphenated/dotted stutters (e.g., 'w-w-water' -> 'water')
          3. Remove punctuation except spaces
          4. Collapse character runs (e.g., 'waaaater' -> 'water')
          5. Expand contractions and spoken shorthand
          6. Filter filler sounds if enabled
          7. Standardize whitespace
        """
        if not text:
            return ""

        # Step 1: Lowercase
        text = text.lower().strip()

        # Step 2: Collapse stutter prefixes: "w-w-water", "w...w...water", "w-water"
        text = self._collapse_stutter_prefixes(text)

        # Step 3: Punctuation removal (keep letters, digits, whitespace)
        text = re.sub(r"[^\w\s]", " ", text)

        # Step 4: Collapse repeated consecutive characters (3+ -> 1 or 2)
        # e.g., 'heeeeelp' -> 'help', 'waaater' -> 'water'
        text = self._collapse_character_runs(text)

        # Step 5: Expand contractions & token replacements
        tokens = text.split()
        expanded_tokens: List[str] = []
        for token in tokens:
            # Map shorthand if exists
            expanded = self.CONTRACTION_MAP.get(token, token)
            # Token could expand to multiple words
            for sub_tok in expanded.split():
                if self.strip_fillers and sub_tok in self.FILLERS:
                    continue
                expanded_tokens.append(sub_tok)

        # Step 6: Deduplicate consecutive identical words (e.g. "water water water" -> "water")
        deduped_tokens: List[str] = []
        for tok in expanded_tokens:
            if not deduped_tokens or tok != deduped_tokens[-1]:
                deduped_tokens.append(tok)

        cleaned_text = " ".join(deduped_tokens)
        return cleaned_text

    def _collapse_stutter_prefixes(self, text: str) -> str:
        """
        Collapses acoustic speech stutters represented as:
        'w-w-water' -> 'water'
        'p-p-please' -> 'please'
        'th-th-thirsty' -> 'thirsty'
        'c...c...cold' -> 'cold'
        """
        # Pattern 1: single or double letter followed by hyphen/dots repeated: (w-)+water -> water
        pattern1 = r"\b([a-z]{1,2})[\-\.]+(?=\1|\w+)"
        cleaned = re.sub(pattern1, "", text)
        return cleaned

    def _collapse_character_runs(self, text: str) -> str:
        """
        Collapses elongated sounds (e.g., 'sooo cooold' -> 'so cold', 'waaaater' -> 'water').
        Reduces 3 or more identical consecutive characters to 1.
        """
        return re.sub(r"([a-z])\1{2,}", r"\1", text)

    @staticmethod
    @lru_cache(maxsize=4096)
    def soundex(word: str) -> str:
        """
        Pure-Python Soundex phonetic encoding.
        Converts a word into a 4-character code (Letter + 3 digits).
        """
        word = re.sub(r"[^a-zA-Z]", "", word).upper()
        if not word:
            return "0000"

        first_char = word[0]
        mapping = {
            "B": "1", "F": "1", "P": "1", "V": "1",
            "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
            "D": "3", "T": "3",
            "L": "4",
            "M": "5", "N": "5",
            "R": "6"
        }

        codes = [first_char]
        prev_code = mapping.get(first_char, "0")

        for char in word[1:]:
            code = mapping.get(char, "0")
            if code != "0" and code != prev_code:
                codes.append(code)
            prev_code = code

        result = "".join(codes)
        # Pad with zeros or truncate to length 4
        result = (result + "0000")[:4]
        return result

    @staticmethod
    @lru_cache(maxsize=4096)
    def metaphone(word: str) -> str:
        """
        Pure-Python simplified Metaphone algorithm for phonetic key matching.
        """
        word = re.sub(r"[^a-zA-Z]", "", word).upper()
        if not word:
            return ""

        # Drop initial silent letters
        if word.startswith(("KN", "GN", "PN", "AE", "WR")):
            word = word[1:]
        elif word.startswith("X"):
            word = "S" + word[1:]
        elif word.startswith("WH"):
            word = "W" + word[2:]

        result = []
        i = 0
        n = len(word)

        while i < n:
            ch = word[i]
            # Skip vowels after first character
            if ch in "AEIOU":
                if i == 0:
                    result.append(ch)
                i += 1
                continue

            # Consonants logic
            if ch == "B":
                if i == n - 1 and i > 0 and word[i - 1] == "M":
                    pass  # 'MB' at end of word (dumb, thumb)
                else:
                    result.append("B")
            elif ch == "C":
                if i + 1 < n and word[i + 1] in "EIY":
                    result.append("S")
                elif i + 1 < n and word[i + 1] == "H":
                    result.append("X")
                    i += 1
                else:
                    result.append("K")
            elif ch == "D":
                if i + 1 < n and word[i + 1] == "G" and i + 2 < n and word[i + 2] in "EIY":
                    result.append("J")
                    i += 2
                else:
                    result.append("T")
            elif ch == "F" or ch == "V":
                result.append("F")
            elif ch == "G":
                if i + 1 < n and word[i + 1] == "H":
                    pass  # silent gh (night, caught)
                elif i + 1 < n and word[i + 1] in "EIY":
                    result.append("J")
                else:
                    result.append("K")
            elif ch == "H":
                if i > 0 and word[i - 1] in "AEIOU" and (i + 1 == n or word[i + 1] not in "AEIOU"):
                    pass  # silent H
                else:
                    result.append("H")
            elif ch == "J":
                result.append("J")
            elif ch == "K":
                if i > 0 and word[i - 1] == "C":
                    pass  # Skip 'CK'
                else:
                    result.append("K")
            elif ch == "L":
                result.append("L")
            elif ch == "M":
                result.append("M")
            elif ch == "N":
                result.append("N")
            elif ch == "P":
                if i + 1 < n and word[i + 1] == "H":
                    result.append("F")
                    i += 1
                else:
                    result.append("P")
            elif ch == "Q":
                result.append("K")
            elif ch == "R":
                result.append("R")
            elif ch == "S":
                if i + 1 < n and word[i + 1] == "H":
                    result.append("X")
                    i += 1
                else:
                    result.append("S")
            elif ch == "T":
                if i + 1 < n and word[i + 1] == "H":
                    result.append("0")  # '0' denotes 'th'
                    i += 1
                elif i + 2 < n and word[i + 1:i + 3] == "IO":
                    result.append("X")
                    i += 2
                else:
                    result.append("T")
            elif ch == "W" or ch == "Y":
                if i + 1 < n and word[i + 1] in "AEIOU":
                    result.append(ch)
            elif ch == "Z":
                result.append("S")

            i += 1

        # Deduplicate consecutive identical codes
        compacted = []
        for code in result:
            if not compacted or code != compacted[-1]:
                compacted.append(code)

        return "".join(compacted)

    def phonetic_tokens(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Returns list of (token, soundex_code, metaphone_code).
        """
        normalized = self.normalize(text)
        tokens = normalized.split()
        return [(t, self.soundex(t), self.metaphone(t)) for t in tokens]
