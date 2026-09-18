"""
PMIR-Net-Lite: Quantitative Benchmark Evaluation & Personalization Assessment Suite.
Computes real empirical metrics:
  - Overall Intent Accuracy (Top-1)
  - Accuracy Stratified by Severity (Clean, Mild, Moderate, Severe)
  - Abstention / Clarification Rate
  - Before vs. After Personalization Accuracy & Confidence Gains

All reported metrics are computed live from executed tests.
"""

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from typing import Dict, List, Any, Tuple

from pmir.matcher import IntentMatcher
from pmir.personal_dictionary import PersonalDictionary
from pmir.simulator import TranscriptDistortionSimulator
from pmir.dialogue import ConfirmationGate, DialogueAction
from pmir.tts import ConsoleTTSProvider


def run_benchmark_evaluation(
    benchmark_path: str,
    intents_path: str,
    abstention_threshold: float = 0.52
) -> Dict[str, Any]:
    """
    Evaluates PMIR matching engine across all synthetic benchmark samples.
    """
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    samples = benchmark_data.get("samples", [])
    if not samples:
        raise ValueError(f"No samples found in {benchmark_path}")

    # Initialize clean matcher without personalization
    empty_dict = PersonalDictionary()
    matcher = IntentMatcher(
        intents_path=intents_path,
        personal_dict=empty_dict,
        abstention_threshold=abstention_threshold
    )

    total_samples = len(samples)
    correct_count = 0
    abstained_count = 0
    correct_non_abstained = 0

    severity_stats = defaultdict(lambda: {
        "total": 0,
        "correct": 0,
        "abstained": 0,
        "correct_non_abstained": 0,
        "confidences": []
    })

    intent_stats = defaultdict(lambda: {"total": 0, "correct": 0, "abstained": 0})
    confusion_pairs = defaultdict(int)

    for item in samples:
        ground_truth = item["ground_truth_intent"]
        severity = item["severity"]
        transcript = item["distorted_transcript"]

        res = matcher.match(transcript)
        pred_intent = res.intent_id
        is_correct = (pred_intent == ground_truth)
        is_abstain = res.is_abstain
        conf = res.confidence

        severity_stats[severity]["total"] += 1
        severity_stats[severity]["confidences"].append(conf)
        intent_stats[ground_truth]["total"] += 1

        if is_correct:
            correct_count += 1
            severity_stats[severity]["correct"] += 1
            intent_stats[ground_truth]["correct"] += 1

        if is_abstain:
            abstained_count += 1
            severity_stats[severity]["abstained"] += 1
            intent_stats[ground_truth]["abstained"] += 1
        else:
            if is_correct:
                correct_non_abstained += 1
                severity_stats[severity]["correct_non_abstained"] += 1
            else:
                confusion_pairs[f"{ground_truth} -> {pred_intent}"] += 1

    overall_top1_accuracy = correct_count / total_samples
    overall_abstention_rate = abstained_count / total_samples
    evaluated_accuracy = (
        correct_non_abstained / (total_samples - abstained_count)
        if (total_samples - abstained_count) > 0 else 0.0
    )

    severity_breakdown = {}
    for sev, st in severity_stats.items():
        tot = st["total"]
        non_abs = tot - st["abstained"]
        sev_top1 = st["correct"] / tot if tot > 0 else 0.0
        sev_abs_rate = st["abstained"] / tot if tot > 0 else 0.0
        sev_clean_acc = st["correct_non_abstained"] / non_abs if non_abs > 0 else 0.0
        avg_conf = sum(st["confidences"]) / len(st["confidences"]) if st["confidences"] else 0.0

        severity_breakdown[sev] = {
            "total_samples": tot,
            "top1_accuracy": round(sev_top1, 4),
            "abstention_rate": round(sev_abs_rate, 4),
            "non_abstained_accuracy": round(sev_clean_acc, 4),
            "average_confidence": round(avg_conf, 4)
        }

    return {
        "total_samples": total_samples,
        "overall_top1_accuracy": round(overall_top1_accuracy, 4),
        "overall_abstention_rate": round(overall_abstention_rate, 4),
        "evaluated_accuracy_excluding_abstentions": round(evaluated_accuracy, 4),
        "severity_breakdown": severity_breakdown,
        "top_confusions": dict(sorted(confusion_pairs.items(), key=lambda x: x[1], reverse=True)[:5])
    }


def run_personalization_experiment(intents_path: str) -> Dict[str, Any]:
    """
    Empirically compares prediction accuracy before and after user confirmation/personalization
    on challenging, idiosyncratic phrase variants.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_dict_path = f.name

    try:
        # Idiosyncratic and highly distorted user-specific phrases
        personalized_eval_set = [
            {"phrase": "wtr cup here", "intent": "NEED_WATER"},
            {"phrase": "aqua plz", "intent": "NEED_WATER"},
            {"phrase": "tummy ouchie badly", "intent": "EXPRESS_PAIN"},
            {"phrase": "head pounding hard", "intent": "EXPRESS_PAIN"},
            {"phrase": "potty assist", "intent": "RESTROOM_ACCESS"},
            {"phrase": "loo right now", "intent": "RESTROOM_ACCESS"},
            {"phrase": "freezing cold toes", "intent": "FEELING_COLD"},
            {"phrase": "aircon off brrr", "intent": "FEELING_COLD"},
            {"phrase": "pillbox noon med", "intent": "TAKE_MEDICATION"},
            {"phrase": "swallow blue tablet", "intent": "TAKE_MEDICATION"},
            {"phrase": "ring my gal sarah", "intent": "CALL_FAMILY"},
            {"phrase": "dial sonny boy", "intent": "CALL_FAMILY"},
            {"phrase": "screen flick movie", "intent": "ENTERTAINMENT_MEDIA"},
            {"phrase": "shut eye time snooze", "intent": "TIRED_SLEEP"},
            {"phrase": "panic 911 urgent", "intent": "EMERGENCY_HELP"},
            {"phrase": "choking air please", "intent": "EMERGENCY_HELP"},
        ]

        # Phase A: BEFORE Personalization (Baseline Empty Dictionary)
        p_dict = PersonalDictionary(filepath=temp_dict_path)
        tts = ConsoleTTSProvider(verbose=False)
        matcher = IntentMatcher(intents_path=intents_path, personal_dict=p_dict)
        gate = ConfirmationGate(matcher=matcher, personal_dict=p_dict, tts=tts)

        before_correct = 0
        before_abstained = 0
        before_confidences = []

        for item in personalized_eval_set:
            res = matcher.match(item["phrase"])
            before_confidences.append(res.confidence)
            if res.intent_id == item["intent"]:
                before_correct += 1
            if res.is_abstain:
                before_abstained += 1

        # Phase B: Personalization Training (Simulating Human Confirmation/Edit Gate)
        for item in personalized_eval_set:
            # User interacts and confirms/edits the phrase mapping
            gate.process_turn(
                raw_input=item["phrase"],
                user_action=DialogueAction.CONFIRM if matcher.match(item["phrase"]).intent_id == item["intent"] else DialogueAction.EDIT,
                corrected_intent_id=item["intent"]
            )

        # Phase C: AFTER Personalization (Re-evaluating with Learned Personal Dictionary)
        after_correct = 0
        after_abstained = 0
        after_confidences = []

        for item in personalized_eval_set:
            res = matcher.match(item["phrase"])
            after_confidences.append(res.confidence)
            if res.intent_id == item["intent"]:
                after_correct += 1
            if res.is_abstain:
                after_abstained += 1

        total = len(personalized_eval_set)
        before_acc = before_correct / total
        after_acc = after_correct / total
        before_avg_conf = sum(before_confidences) / total
        after_avg_conf = sum(after_confidences) / total

        return {
            "total_test_phrases": total,
            "before_accuracy": round(before_acc, 4),
            "after_accuracy": round(after_acc, 4),
            "accuracy_delta": round(after_acc - before_acc, 4),
            "before_abstention_rate": round(before_abstained / total, 4),
            "after_abstention_rate": round(after_abstained / total, 4),
            "before_avg_confidence": round(before_avg_conf, 4),
            "after_avg_confidence": round(after_avg_conf, 4),
            "confidence_gain": round(after_avg_conf - before_avg_conf, 4)
        }

    finally:
        if os.path.exists(temp_dict_path):
            os.remove(temp_dict_path)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="PMIR-Net-Lite Evaluation Suite")
    parser.add_argument("--generate", action="store_true", help="Regenerate synthetic benchmark dataset")
    parser.add_argument("--samples", type=int, default=16, help="Samples per intent for generation (default: 16)")
    parser.add_argument("--threshold", type=float, default=0.52, help="Abstention confidence threshold")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    intents_path = os.path.join(base_dir, "data", "intents.json")
    benchmark_path = os.path.join(base_dir, "data", "simulated_benchmark.json")

    # Step 1: Benchmark Dataset Generation
    if args.generate or not os.path.exists(benchmark_path):
        print("\n=======================================================")
        print("  GENERATING SIMULATED BENCHMARK DATASET")
        print("  Notice: All data procedurally simulated. 'data_source': 'SIMULATED'")
        print("=======================================================")
        sim = TranscriptDistortionSimulator(seed=42)
        gen_meta = sim.generate_benchmark(
            intents_path=intents_path,
            output_path=benchmark_path,
            samples_per_intent=args.samples
        )
        print(f"[+] Generated {gen_meta['metadata']['total_samples']} samples across 18 intents.")
        print(f"[+] Saved benchmark to {benchmark_path}\n")

    # Step 2: Run Baseline Benchmark Evaluation
    print("=======================================================")
    print("  RUNNING EMPIRICAL BENCHMARK EVALUATION")
    print(f"  Abstention Threshold (tau): {args.threshold:.2f}")
    print("=======================================================")

    bench_results = run_benchmark_evaluation(
        benchmark_path=benchmark_path,
        intents_path=intents_path,
        abstention_threshold=args.threshold
    )

    print(f"\n[REPORT] OVERALL BENCHMARK RESULTS ({bench_results['total_samples']} Simulated Transcripts):")
    print(f"   * Overall Top-1 Intent Accuracy : {bench_results['overall_top1_accuracy']:.1%}")
    print(f"   * Abstention / Clarify Rate     : {bench_results['overall_abstention_rate']:.1%}")
    print(f"   * Accuracy on Accepted Matches  : {bench_results['evaluated_accuracy_excluding_abstentions']:.1%}")

    print("\n[BREAKDOWN] STRATIFIED ACCURACY BY SEVERITY TIER:")
    print("   " + "-" * 72)
    print(f"   {'Severity':<12} | {'Samples':<8} | {'Top-1 Acc':<10} | {'Abstain %':<10} | {'Accepted Acc':<12} | {'Avg Conf':<8}")
    print("   " + "-" * 72)
    for sev, stats in bench_results["severity_breakdown"].items():
        print(
            f"   {sev.capitalize():<12} | "
            f"{stats['total_samples']:<8} | "
            f"{stats['top1_accuracy']:<10.1%} | "
            f"{stats['abstention_rate']:<10.1%} | "
            f"{stats['non_abstained_accuracy']:<12.1%} | "
            f"{stats['average_confidence']:<8.3f}"
        )
    print("   " + "-" * 72)

    if bench_results["top_confusions"]:
        print("\n[ANALYSIS] NOTABLE MISCLASSIFICATIONS (Ground Truth -> Predicted):")
        for pair, count in bench_results["top_confusions"].items():
            print(f"   * {pair} : {count} instances")

    # Step 3: Run Personalization Experiment
    print("\n=======================================================")
    print("  RUNNING PERSONALIZATION ADAPTATION EXPERIMENT")
    print("  Testing before vs. after user-confirmed adaptation")
    print("=======================================================")

    p_results = run_personalization_experiment(intents_path=intents_path)

    print(f"\n[RESULT] PERSONALIZATION RESULTS ({p_results['total_test_phrases']} Idiosyncratic Phrases):")
    print(f"   * Baseline Accuracy (Before Personalization) : {p_results['before_accuracy']:.1%}")
    print(f"   * Adapted Accuracy  (After Personalization)  : {p_results['after_accuracy']:.1%}")
    print(f"   * Accuracy Delta                             : +{p_results['accuracy_delta']:.1%}")
    print(f"   * Abstention Rate (Before -> After)          : {p_results['before_abstention_rate']:.1%} -> {p_results['after_abstention_rate']:.1%}")
    print(f"   * Average Confidence (Before -> After)       : {p_results['before_avg_confidence']:.3f} -> {p_results['after_avg_confidence']:.3f} (+{p_results['confidence_gain']:.3f})")

    # Save summary report
    summary_path = os.path.join(base_dir, "benchmark_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark_evaluation": bench_results,
            "personalization_experiment": p_results
        }, f, indent=2)
    print(f"\n[+] Saved evaluation artifact to {summary_path}\n")


if __name__ == "__main__":
    main()
