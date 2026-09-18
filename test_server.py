"""
PMIR-Net-Lite: Web Server & REST API Tests.
Validates endpoints: /api/intents, /api/predict, /api/action, /api/dictionary, /api/benchmark.
"""

import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import HTTPServer

from pmir.pipeline import PMIRPipeline
from server import PMIRRequestHandler


class TestPMIRServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp()
        cls.dict_path = os.path.join(cls.test_dir, "test_dict.json")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.static_dir = os.path.join(base_dir, "frontend")

        cls.pipeline = PMIRPipeline(personal_dict_path=cls.dict_path)
        PMIRRequestHandler.pipeline = cls.pipeline
        PMIRRequestHandler.static_dir = cls.static_dir

        cls.port = 8765
        cls.server = HTTPServer(("127.0.0.1", cls.port), PMIRRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if resp.headers.get_content_type() == "application/json" else data

    def _post(self, path: str, payload: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def test_get_intents(self):
        status, data = self._get("/api/intents")
        self.assertEqual(status, 200)
        self.assertIn("intents", data)
        self.assertEqual(len(data["intents"]), 18)

    def test_predict_distorted_input(self):
        status, data = self._post("/api/predict", {"text": "w-w-wader plz"})
        self.assertEqual(status, 200)
        self.assertEqual(data["predicted_intent"], "NEED_WATER")
        self.assertFalse(data["is_abstain"])
        self.assertGreater(data["confidence"], 0.70)
        self.assertIn("phonetic_tokens", data)

    def test_confirm_action_and_dictionary_update(self):
        status, data = self._post("/api/action", {"text": "gimme wtr", "action": "CONFIRM"})
        self.assertEqual(status, 200)
        self.assertTrue(data["dictionary_updated"])
        self.assertTrue(data["tts_spoken"])
        self.assertEqual(data["final_intent_id"], "NEED_WATER")

        # Verify entry exists in dictionary
        d_status, d_data = self._get("/api/dictionary")
        self.assertEqual(d_status, 200)
        phrases = [e["phrase"] for e in d_data["entries"]]
        self.assertIn("gimme wtr", phrases)


if __name__ == "__main__":
    unittest.main()

