import csv
import sys
import time
from pathlib import Path

# Ensure src is importable when running this script directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.decision import make_decision

DATA_PATH = Path(__file__).parent.parent / "data" / "tickets.csv"

# Gemini free tier allows 5 requests/minute for embedding + generation combined.
# Each test case makes 2 calls (1 embed for retrieval, 1 generate for decision),
# so we stay well under quota with a delay between test cases.
DELAY_BETWEEN_CASES_SECONDS = 20
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 65


def load_test_cases():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def make_decision_with_retry(message: str):
    """Retries on rate-limit errors with a backoff delay."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return make_decision(message)
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                print(f"    Rate limited, waiting {RETRY_BACKOFF_SECONDS}s before retry ({attempt}/{MAX_RETRIES})...")
                time.sleep(RETRY_BACKOFF_SECONDS)
            else:
                raise
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries due to rate limiting.")


def run_evaluation():
    test_cases = load_test_cases()
    total = len(test_cases)
    correct = 0
    results = []

    for i, case in enumerate(test_cases, start=1):
        message = case["message"]
        expected = case["expected_action"]

        print(f"[{i}/{total}] Running: {message[:60]}...")
        try:
            decision = make_decision_with_retry(message)
            actual = decision.action
            confidence = decision.confidence
        except Exception as e:
            print(f"    FAILED: {e}")
            actual = "ERROR"
            confidence = 0.0

        is_correct = actual == expected
        correct += int(is_correct)

        results.append({
            "message": message,
            "expected": expected,
            "actual": actual,
            "confidence": confidence,
            "correct": is_correct,
        })

        # Avoid hitting rate limits on the next iteration
        if i < total:
            time.sleep(DELAY_BETWEEN_CASES_SECONDS)
    accuracy = (correct / total * 100) if total else 0

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    for r in results:
        status = "✓" if r["correct"] else "✗"
        print(f"{status} [{r['expected']:<25} vs {r['actual']:<25}] conf={r['confidence']:.2f}")
        print(f"    {r['message'][:80]}")

    print("\n" + "-" * 70)
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {total - correct}")
    print(f"Accuracy: {accuracy:.1f}%")
    print("-" * 70)

    return results


if __name__ == "__main__":
    run_evaluation()