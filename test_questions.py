"""
Fixed test set for the naive-vs-verified comparison.

Deliberately mixes:
- questions with well-documented official answers (should find Tier 1
  sources easily)
- security-sensitive questions (where a Tier-3-only answer is most
  likely to be actively wrong/incomplete, not just "less confident")
- a couple of fast-moving-ecosystem questions (higher chance of stale
  blog advice)

Run each question through BOTH answer_with_search() (03_real_search.py)
and answer_naively() (naive_baseline.py), then manually review the
outputs side by side. This script just prints the list — running it
against both pipelines is a manual step for now (automating that
comparison harness is a reasonable next addition once you've eyeballed
a few by hand and know what you're looking for).
"""

TEST_QUESTIONS = [
    "What is the current recommended way to validate file uploads in Node.js?",
    "What is the current recommended way to hash passwords in Node.js?",
    "What is the best way to prevent SQL injection in a Node.js Express app?",
    "What is the current recommended way to handle CORS in an Express API?",
    "What is the recommended way to store JWT tokens on the client side?",
    "What is the current best practice for rate limiting an Express API?",
    "What is the recommended way to sanitize user input to prevent XSS in React?",
    "What is the current recommended state management approach for React in 2026?",
]

if __name__ == "__main__":
    print(f"{len(TEST_QUESTIONS)} test questions:\n")
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"{i}. {q}")
    print(
        "\nRun each of these through both:\n"
        "  python 03_real_search.py   (edit the __main__ line to loop over these)\n"
        "  python naive_baseline.py   (same)\n"
        "Then compare skills.jsonl vs naive_skills.jsonl for the same skill_id."
    )