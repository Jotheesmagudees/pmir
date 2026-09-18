"""
PMIR-Net-Lite: Personal Dictionary Module.
Inspectable, user-editable persistent store for user-confirmed phrase-to-intent mappings.
Strict safety constraint: No phrase is ever added automatically without explicit user confirmation/edit.
"""

import json
import os
import time
from typing import Dict, List, Optional, Any


class PersonalDictionary:
    """
    Manages personalized phrase mappings for an individual user.
    Additive and inspectable: only user-confirmed phrase -> intent pairs are stored.
    """

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath
        # Mappings structure: { normalized_phrase: { "intent_id": str, "timestamp": str, "usage_count": int, "note": str } }
        self.entries: Dict[str, Dict[str, Any]] = {}
        if self.filepath and os.path.exists(self.filepath):
            self.load(self.filepath)

    def add_entry(self, raw_phrase: str, intent_id: str, note: str = "") -> bool:
        """
        Adds or updates a confirmed phrase -> intent mapping.
        Always normalizes the phrase key.
        """
        phrase_key = raw_phrase.strip().lower()
        if not phrase_key or not intent_id:
            return False

        existing = self.entries.get(phrase_key)
        count = (existing.get("usage_count", 0) + 1) if existing else 1

        self.entries[phrase_key] = {
            "intent_id": intent_id,
            "raw_example": raw_phrase.strip(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "usage_count": count,
            "note": note or "User confirmed via PMIR dialogue"
        }

        if self.filepath:
            self.save(self.filepath)
        return True

    def get_entry(self, raw_phrase: str) -> Optional[Dict[str, Any]]:
        """Retrieves exact personal dictionary record if exists."""
        phrase_key = raw_phrase.strip().lower()
        return self.entries.get(phrase_key)

    def remove_entry(self, raw_phrase: str) -> bool:
        """Removes a personalized phrase mapping."""
        phrase_key = raw_phrase.strip().lower()
        if phrase_key in self.entries:
            del self.entries[phrase_key]
            if self.filepath:
                self.save(self.filepath)
            return True
        return False

    def list_entries(self) -> List[Dict[str, Any]]:
        """Returns all personalized entries for inspection."""
        records = []
        for phrase, data in self.entries.items():
            records.append({
                "phrase": phrase,
                "intent_id": data["intent_id"],
                "usage_count": data.get("usage_count", 1),
                "timestamp": data.get("timestamp", ""),
                "note": data.get("note", "")
            })
        return records

    def save(self, filepath: Optional[str] = None) -> None:
        """Saves personal dictionary to JSON file."""
        target = filepath or self.filepath
        if not target:
            return
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        payload = {
            "version": "1.0.0",
            "metadata": {
                "total_personalized_phrases": len(self.entries),
                "last_modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            },
            "entries": self.entries
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self, filepath: Optional[str] = None) -> None:
        """Loads personal dictionary from JSON file."""
        target = filepath or self.filepath
        if not target or not os.path.exists(target):
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entries = data.get("entries", {})
        except Exception as e:
            print(f"[Warning] Could not load personal dictionary from {target}: {e}")
            self.entries = {}

    def clear(self) -> None:
        """Clears all entries in memory and on disk."""
        self.entries = {}
        if self.filepath and os.path.exists(self.filepath):
            self.save(self.filepath)

