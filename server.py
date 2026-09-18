"""
PMIR-Net-Lite: Web Server & REST API.
Provides zero-dependency REST endpoints for intent prediction,
dialogue confirmation gate, personal dictionary management, and benchmark stats.
"""

import json
import mimetypes
import os
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from pmir.pipeline import PMIRPipeline
from pmir.dialogue import DialogueAction


class PMIRRequestHandler(BaseHTTPRequestHandler):
    """Handles REST API requests and static asset serving for PMIR Web UI."""

    pipeline: PMIRPipeline = None
    static_dir: str = ""

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def _parse_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            body_bytes = self.rfile.read(content_length)
            return json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return {}

    def _send_json(self, data: Any, status_code: int = 200):
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/intents":
            intents_data = [
                {
                    "id": k,
                    "canonical_label": v.get("canonical_label", k),
                    "category": v.get("category", "General"),
                    "tts_response": v.get("tts_response", ""),
                    "urgency": v.get("urgency", "medium"),
                    "base_phrases": v.get("base_phrases", [])
                }
                for k, v in self.pipeline.matcher.intents.items()
            ]
            self._send_json({"intents": intents_data})

        elif path == "/api/dictionary":
            entries = self.pipeline.list_personal_dictionary()
            self._send_json({"entries": entries, "count": len(entries)})

        elif path == "/api/benchmark":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            results_path = os.path.join(base_dir, "benchmark_results.json")
            if os.path.exists(results_path):
                with open(results_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            else:
                self._send_json({"error": "Benchmark results not yet generated."}, 404)

        else:
            # Serve static files from static_dir
            if path == "/" or path == "":
                rel_path = "index.html"
            else:
                rel_path = path.lstrip("/")

            safe_path = os.path.abspath(os.path.join(self.static_dir, rel_path))
            if safe_path.startswith(os.path.abspath(self.static_dir)) and os.path.exists(safe_path) and os.path.isfile(safe_path):
                mime, _ = mimetypes.guess_type(safe_path)
                mime = mime or "application/octet-stream"
                self._set_headers(200, mime)
                with open(safe_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._parse_body()

        if path == "/api/predict":
            raw_text = body.get("text", "").strip()
            if not raw_text:
                self._send_json({"error": "Missing 'text' field"}, 400)
                return

            res = self.pipeline.predict(raw_text)
            normalized = self.pipeline.normalizer.normalize(raw_text)
            phonetic_tokens = [
                {
                    "token": t,
                    "soundex": self.pipeline.normalizer.soundex(t),
                    "metaphone": self.pipeline.normalizer.metaphone(t)
                }
                for t in normalized.split()
            ]

            payload = {
                "raw_text": raw_text,
                "normalized_text": normalized,
                "phonetic_tokens": phonetic_tokens,
                "predicted_intent": res.intent_id,
                "canonical_label": res.canonical_label,
                "confidence": res.confidence,
                "is_personal": res.is_personal,
                "is_abstain": res.is_abstain,
                "tts_response": res.tts_response,
                "urgency": res.urgency,
                "clarification_prompt": res.clarification_prompt,
                "top_alternatives": res.top_alternatives,
                "score_breakdown": res.score_breakdown
            }
            self._send_json(payload)

        elif path == "/api/action":
            raw_text = body.get("text", "").strip()
            action_str = body.get("action", "CONFIRM").upper()
            corrected_id = body.get("corrected_intent_id")

            if not raw_text:
                self._send_json({"error": "Missing 'text' field"}, 400)
                return

            try:
                action = DialogueAction(action_str)
            except ValueError:
                self._send_json({"error": f"Invalid action '{action_str}'"}, 400)
                return

            result = self.pipeline.process(
                raw_transcript=raw_text,
                action=action,
                corrected_intent_id=corrected_id
            )

            response_data = {
                "action_taken": result["action_taken"].value,
                "dictionary_updated": result["dictionary_updated"],
                "tts_spoken": result["tts_spoken"],
                "final_intent_id": result["final_intent_id"],
                "final_tts_text": result["final_tts_text"],
                "dictionary_count": len(self.pipeline.personal_dict.entries)
            }
            self._send_json(response_data)

        elif path == "/api/dictionary/add":
            phrase = body.get("phrase", "").strip()
            intent_id = body.get("intent_id", "").strip()
            note = body.get("note", "Manual entry via Web UI")

            if not phrase or not intent_id:
                self._send_json({"error": "Phrase and Intent ID required"}, 400)
                return

            success = self.pipeline.personal_dict.add_entry(phrase, intent_id, note=note)
            self._send_json({"success": success, "phrase": phrase, "intent_id": intent_id})

        else:
            self._send_json({"error": "Unknown POST endpoint"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/dictionary":
            query = urllib.parse.parse_qs(parsed.query)
            phrase = query.get("phrase", [None])[0]

            if phrase:
                success = self.pipeline.personal_dict.remove_entry(phrase)
                self._send_json({"success": success, "phrase": phrase})
            else:
                self.pipeline.clear_personal_dictionary()
                self._send_json({"success": True, "message": "Personal dictionary cleared"})
        else:
            self._send_json({"error": "Unknown DELETE endpoint"}, 404)


def run_server(port: int = 8000):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(base_dir, "frontend")
    os.makedirs(static_dir, exist_ok=True)

    pipeline = PMIRPipeline()

    PMIRRequestHandler.pipeline = pipeline
    PMIRRequestHandler.static_dir = static_dir

    server_address = ("", port)
    httpd = HTTPServer(server_address, PMIRRequestHandler)

    print("=" * 65)
    print(f"  PMIR-Net-Lite Web Interface Running at: http://localhost:{port}")
    print(f"  Serving static files from: {static_dir}")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)

