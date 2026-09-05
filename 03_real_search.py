"""
Step 3 — Real search, wired into the working text-protocol loop.

Requires: pip install tavily-python
Set your API key: set TAVILY_API_KEY=your_key_here   (Windows)
                   export TAVILY_API_KEY=your_key_here (Mac/Linux)

Run: python 03_real_search.py
"""

import os
import re
import requests
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()  # reads .env in the working directory into os.environ

LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
SEARCH_PATTERN = re.compile(r"^SEARCH:\s*(.+)$", re.MULTILINE)

# Tier 1: official docs / authoritative standards bodies for the domains we
# expect to search (extend this list as you hit new domains in testing).
TIER_1_DOMAINS = [
    "nodejs.org", "expressjs.com", "developer.mozilla.org", "owasp.org",
    "reactjs.org", "react.dev", "npmjs.com", "github.com",
]
# Tier 2: established, edited technical publications (not personal blogs).
TIER_2_DOMAINS = [
    "digitalocean.com", "freecodecamp.org", "smashingmagazine.com",
]
# Everything else (personal blogs, Medium, dev.to, random sites) is Tier 3.


def classify_domain(url: str) -> int:
    for d in TIER_1_DOMAINS:
        if d in url:
            return 1
    for d in TIER_2_DOMAINS:
        if d in url:
            return 2
    return 3


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
    raise RuntimeError(
        "TAVILY_API_KEY not found. Create a .env file (see .env.example) "
        "with TAVILY_API_KEY=your_key_here — never hardcode it in the script."
    )
tavily = TavilyClient(api_key=tavily_key)


def call_model(messages: list) -> str:
    resp = requests.post(
        LLAMA_SERVER_URL,
        json={"messages": messages, "temperature": 0.1, "max_tokens": 300},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def real_web_search(query: str, max_results: int = 3) -> tuple[str, int]:
    """
    Real search via Tavily. Returns (digest text for the model, best tier found)
    so the caller can decide whether to trust a confident answer or flag it.
    """
    results = tavily.search(query=query, max_results=max_results)
    lines = []
    best_tier = 3
    for r in results.get("results", []):
        tier = classify_domain(r["url"])
        best_tier = min(best_tier, tier)
        lines.append(f"- [Tier {tier}] {r['title']} ({r['url']})\n  {r['content'][:300]}")
    digest = "\n".join(lines) if lines else "No results found."
    return digest, best_tier


def answer_with_search(task: str):
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
    search_results, best_tier = real_web_search(query)
    print(f"\n--- Search results (best tier found: {best_tier}) ---\n{search_results}\n----------------------\n")

    confidence_note = (
        "All sources found are Tier 3 (unverified — personal blogs, forums, etc). "
        "You MUST caveat your answer as provisional and note it hasn't been "
        "checked against official documentation."
        if best_tier == 3
        else "At least one Tier 1/2 (official docs or established publication) "
        "source was found — you can answer with normal confidence."
    )

    messages.append({"role": "assistant", "content": first_response})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Here are the search results:\n\n{search_results}\n\n"
                f"Source quality note: {confidence_note}\n\n"
                f"Now answer the original question: {task}\n"
                "Base your answer only on these results. If they don't fully "
                "answer it, say what's still uncertain rather than guessing."
            ),
        }
    )
    final_answer = call_model(messages).strip()

    # Don't rely on the model to remember to caveat itself — we already know
    # the tier objectively, so enforce the disclaimer in code, not prompting.
    if best_tier == 3:
        final_answer = (
            "⚠️ UNVERIFIED — all sources were Tier 3 (blogs/forums, no official "
            "docs found). Treat this as a starting point, not confirmed guidance:\n\n"
            + final_answer
        )

    print("Final answer:")
    print(final_answer)


if __name__ == "__main__":
    answer_with_search("What is the current recommended way to validate file uploads in Node.js?")