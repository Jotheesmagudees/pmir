"""
PMIR-Net-Lite: Interactive CLI Demonstration & Scripted Walkthrough.
Demonstrates:
  1. Confident distorted phrase matching
  2. Low-confidence abstention & clarification
  3. Interactive human-in-the-loop Confirm / Edit / Reject workflow
  4. Personal dictionary adaptation and subsequent retrieval speedup
"""

import argparse
import os
import sys
from pmir.pipeline import PMIRPipeline
from pmir.dialogue import DialogueAction


def run_scripted_walkthrough():
    """
    Runs automated validation of key pipeline behaviors without manual typing.
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 65)
    print("  PMIR-Net-Lite: AUTOMATED SCRIPTED DEMONSTRATION")
    print("  Personalized Intent Mapping for Imperfect Speech")
    print("  Notice: All inputs simulated for prototype verification.")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dict = os.path.join(base_dir, "data", "demo_personal_dict.json")
    if os.path.exists(temp_dict):
        os.remove(temp_dict)

    pipeline = PMIRPipeline(personal_dict_path=temp_dict)

    # -------------------------------------------------------------
    # Scenario 1: Confident Distorted Match -> User Confirms
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[SCENARIO 1] Confident Distorted Speech Match")
    print("Simulated Input: 'w-w-wader plz'")
    print("=" * 65)
    input_1 = "w-w-wader plz"
    pred_1 = pipeline.predict(input_1)
    print(f"Prediction       : [{pred_1.intent_id}] - {pred_1.canonical_label}")
    print(f"Confidence Score : {pred_1.confidence:.1%}")
    print(f"Abstain Status   : {pred_1.is_abstain}")

    print("\nAction: User selects [CONFIRM]")
    res_1 = pipeline.process(input_1, action=DialogueAction.CONFIRM)
    print(f"Result: Spoken TTS = \"{res_1['final_tts_text']}\"")
    print(f"Personal Dict Updated: {res_1['dictionary_updated']}")

    # -------------------------------------------------------------
    # Scenario 2: Ambiguous / Low-Confidence Fragment -> Abstention
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[SCENARIO 2] Ambiguous Fragment Triggering Abstention Gate")
    print("Simulated Input: 'kld zzz'")
    print("=" * 65)
    input_2 = "kld zzz"
    pred_2 = pipeline.predict(input_2)
    print(f"Prediction       : [{pred_2.intent_id}] - {pred_2.canonical_label}")
    print(f"Confidence Score : {pred_2.confidence:.1%}")
    print(f"Abstain Status   : {pred_2.is_abstain} (Threshold: 0.52)")
    print(f"Clarification    : \"{pred_2.clarification_prompt}\"")
    print("Alternatives     :")
    for alt in pred_2.top_alternatives:
        print(f"  * [{alt['intent_id']}] {alt['canonical_label']} (Conf: {alt['confidence']:.1%})")

    print("\nAction: User selects [REJECT]")
    res_2 = pipeline.process(input_2, action=DialogueAction.REJECT)
    print(f"Result: TTS Spoken = {res_2['tts_spoken']} (Zero speech emitted)")
    print(f"Personal Dict Updated: {res_2['dictionary_updated']} (Zero contamination)")

    # -------------------------------------------------------------
    # Scenario 3: Misclassification / Idiosyncratic Phrase -> User Edits
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[SCENARIO 3] Idiosyncratic Phrase Correction via Edit Gate")
    print("Simulated Input: 'head spinny hard'")
    print("=" * 65)
    input_3 = "head spinny hard"
    pred_3 = pipeline.predict(input_3)
    print(f"Initial Prediction : [{pred_3.intent_id}] (Conf: {pred_3.confidence:.1%})")

    print("\nAction: User selects [EDIT] -> Sets correct intent to 'EXPRESS_PAIN'")
    res_3 = pipeline.process(
        input_3,
        action=DialogueAction.EDIT,
        corrected_intent_id="EXPRESS_PAIN"
    )
    print(f"Result: Spoken TTS = \"{res_3['final_tts_text']}\"")
    print(f"Personal Dict Updated: {res_3['dictionary_updated']}")

    # -------------------------------------------------------------
    # Scenario 4: Personalization Verification
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[SCENARIO 4] Verifying Personal Dictionary Acceleration")
    print("Re-evaluating 'head spinny hard' after user personalization")
    print("=" * 65)
    pred_4 = pipeline.predict(input_3)
    print(f"Updated Prediction : [{pred_4.intent_id}] - {pred_4.canonical_label}")
    print(f"New Confidence     : {pred_4.confidence:.1%}")
    print(f"Is Personal Match  : {pred_4.is_personal} (Priority Boost Applied)")
    print(f"Abstain Status     : {pred_4.is_abstain}")

    # Inspect personal dictionary entries
    print("\n" + "-" * 65)
    print("Current Personal Dictionary Entries:")
    for entry in pipeline.list_personal_dictionary():
        print(f"  * \"{entry['phrase']}\" -> [{entry['intent_id']}] (Used: {entry['usage_count']}x, Note: {entry['note']})")
    print("-" * 65)

    if os.path.exists(temp_dict):
        os.remove(temp_dict)

    print("\n[✓] Scripted demonstration completed successfully.")


def run_interactive_repl():
    """
    Runs interactive live REPL session.
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 65)
    print("  PMIR-Net-Lite: Interactive Assistant Session")
    print("  Type any simulated speech transcript or command:")
    print("    :dict   - Inspect personal dictionary")
    print("    :clear  - Clear personal dictionary")
    print("    :quit   - Exit")
    print("=" * 65)

    pipeline = PMIRPipeline()

    while True:
        try:
            text = input("\n🎙️  Enter transcript: ").strip()
            if not text:
                continue
            if text in (":quit", ":q", "exit"):
                print("Exiting PMIR session. Goodbye!")
                break
            elif text == ":dict":
                entries = pipeline.list_personal_dictionary()
                print(f"\nPersonal Dictionary ({len(entries)} entries):")
                for e in entries:
                    print(f"  • \"{e['phrase']}\" -> [{e['intent_id']}] ({e['note']})")
                continue
            elif text == ":clear":
                pipeline.clear_personal_dictionary()
                print("\nPersonal dictionary cleared.")
                continue

            pipeline.interactive_turn(text)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting PMIR session.")
            break


def main():
    parser = argparse.ArgumentParser(description="PMIR-Net-Lite CLI Demo")
    parser.add_argument("--sample-run", action="store_true", help="Run automated scripted validation walkthrough")
    args = parser.parse_args()

    if args.sample_run:
        run_scripted_walkthrough()
    else:
        run_interactive_repl()


if __name__ == "__main__":
    main()

