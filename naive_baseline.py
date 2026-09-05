"""
Naive baseline — for the comparison study only.

Same search + model as 03_real_search.py, but deliberately WITHOUT:
- trust-tiering shown to the model
- the unverified-source disclaimer
- the syntax check
- any confidence gating in what gets stored

This represents "an agent that searches and stores whatever it finds,
with no verification" — the thing the whole research question is
measuring against. Don't add any of the checks from 03_real_search.py
here; that would defeat the point of having a baseline.

Run: python naive_baseline.py
"""

import os
import re
import json
import datetime
import hashlib
from pathlib import Path
import requests
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
SEARCH_PATTERN = re.compile(r"^SEARCH:\s*(.+)$", re.MULTILINE)
NAIVE_SKILLS_FILE = Path("naive_skills.jsonl")

# Deliberately simple prompt — no source-quality awareness at all, since
# a naive system wouldn't have it.
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

tavily_key = os.environ.get("TAVILY_API_KEY")
if not tavily_key:
    raise RuntimeError("TAVILY_API_KEY not found — see .env.example")
tavily = TavilyClient(api_key=tavily_key)


def call_model(messages: list) -> str:
    resp = requests.post(
        LLAMA_SERVER_URL,
        json={"messages": messages, "temperature": 0.1, "max_tokens": 300},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def naive_search(query: str, max_results: int = 3) -> tuple[str, list[str], int]:
    """
    Returns (digest, urls, true_tier). true_tier is computed ONLY for our
    own later analysis — it is never shown to the model and never affects
    the answer or the stored confidence. That's the whole point of "naive."
    """
    results = tavily.search(query=query, max_results=max_results)
    lines, urls = [], []
    tier_1 = ["nodejs.org", "expressjs.com", "developer.mozilla.org", "owasp.org",
              "reactjs.org", "react.dev", "npmjs.com", "github.com"]
    tier_2 = ["digitalocean.com", "freecodecamp.org", "smashingmagazine.com"]
    true_best_tier = 3
    for r in results.get("results", []):
        url = r["url"]
        tier = 1 if any(d in url for d in tier_1) else 2 if any(d in url for d in tier_2) else 3
        true_best_tier = min(true_best_tier, tier)
        urls.append(url)
        lines.append(f"- {r['title']} ({url})\n  {r['content'][:300]}")
    return ("\n".join(lines) if lines else "No results found."), urls, true_best_tier


def save_naive(query: str, answer: str, urls: list[str], true_tier: int):
    record = {
        "skill_id": hashlib.sha256(query.encode()).hexdigest()[:12],
        "query": query,
        "answer": answer,
        "source_urls": urls,
        "confidence": "trusted",  # naive system always trusts what it finds
        "_true_tier_for_analysis_only": true_tier,  # not used by the pipeline itself
        "learned_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    with NAIVE_SKILLS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def answer_naively(task: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    first_response = call_model(messages).strip()
    match = SEARCH_PATTERN.match(first_response)

    if not match:
        print("Model answered directly without searching:")
        print(first_response)
        return

    query = match.group(1).strip('"')
    print(f"Model wants to search: {query!r}")
    search_results, urls, true_tier = naive_search(query)

    messages.append({"role": "assistant", "content": first_response})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Here are the search results:\n\n{search_results}\n\n"
                f"Now answer the original question: {task}"
                # Note: no source-quality note, no uncertainty instruction —
                # naive system just answers.
            ),
        }
    )
    final_answer = call_model(messages).strip()
    print("Final answer (naive — no disclaimers, no checks):")
    print(final_answer)

    save_naive(task, final_answer, urls, true_tier)
    print(f"\n[Saved to naive_skills.jsonl] confidence=trusted (true source tier was {true_tier}, "
          f"but the pipeline never checked or showed this)")


if __name__ == "__main__":
    from test_questions import TEST_QUESTIONS
    for q in TEST_QUESTIONS:
        print(f"\n{'='*70}\n{q}\n{'='*70}")
        answer_naively(q)