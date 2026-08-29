"""
Step 2c — Text-protocol tool triggering (no OpenAI tools/tool_calls API).

Rationale: llama.cpp's own docs only list native tool-calling as
verified at Qwen2.5-7B+, not 1.5B. Our 0/5 results across two prompt
strategies, with the model verbally acknowledging it should search but
never emitting a structured or even raw-text tool call, suggests this
is a capability limit at this size — not a fixable prompt issue.

Fix: instead of asking the model to conform to a JSON function-call
schema, ask it to output one exact plain-text line when it wants to
search. This is a much simpler pattern for a small model to learn and
follow, and we parse it ourselves in Python — no reliance on
llama.cpp's tool-call parser or the model's schema adherence at all.

Run: python 02c_text_protocol.py
"""

import re
import requests

LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

SEARCH_PATTERN = re.compile(r"^SEARCH:\s*(.+)$", re.MULTILINE)

SYSTEM_PROMPT = (
    "You cannot know anything current or 'best practice' from memory alone — "
    "your training data is outdated for fast-moving topics.\n\n"
    "If the user's question involves current, recommended, latest, or best "
    "practices, you MUST respond with EXACTLY one line and nothing else:\n"
    "SEARCH: <your search query>\n\n"
    "Do not explain, do not answer the question, do not add anything else. "
    "Just that one line. You will get the search results in the next turn "
    "and can answer then."
)


def call_model(task: str) -> str:
    resp = requests.post(
        LLAMA_SERVER_URL,
        json={
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ],
            "temperature": 0.1,  # low — we want exact format compliance, not variety
            "max_tokens": 100,   # a SEARCH line is short; caps runaway generation
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def run_test(task: str, n_trials: int = 5):
    successes = 0
    for i in range(n_trials):
        content = call_model(task).strip()
        match = SEARCH_PATTERN.match(content)
        if match:
            successes += 1
            print(f"[trial {i+1}] OK — wants to search: {match.group(1)!r}")
        else:
            print(f"[trial {i+1}] FAIL — didn't use the SEARCH: format:")
            print(f"  {content[:200]}")

    print(f"\n{successes}/{n_trials} trials used the search protocol correctly.")
    if successes >= 4:
        print("Reliable enough to build on. Next: wire in a real search call and")
        print("feed results back as the next user turn, then re-ask for the answer.")
    else:
        print("Still unreliable. If this fails too, the honest conclusion is that")
        print("1.5B is under-powered for spontaneous tool-use decisions even with")
        print("the simplest possible protocol — worth testing the same script")
        print("against a larger model (even a free API-hosted 7B+) to confirm")
        print("it's a size ceiling, not a technique problem.")


if __name__ == "__main__":
    run_test("What is the current recommended way to validate file uploads in Node.js?")