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
from tavily import TavilyClient

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

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])  # fails loudly if unset — don't hardcode keys


def call_model(messages: list) -> str:
    resp = requests.post(
        LLAMA_SERVER_URL,
        json={"messages": messages, "temperature": 0.1, "max_tokens": 300},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def real_web_search(query: str, max_results: int = 3) -> str:
    """Real search via Tavily. Returns a plain-text digest for the model to read."""
    results = tavily.search(query=query, max_results=max_results)
    lines = []
    for r in results.get("results", []):
        lines.append(f"- {r['title']} ({r['url']})\n  {r['content'][:300]}")
    return "\n".join(lines) if lines else "No results found."


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
    search_results = real_web_search(query)
    print(f"\n--- Search results ---\n{search_results}\n----------------------\n")

    # Feed results back as the next turn and ask for a final answer.
    messages.append({"role": "assistant", "content": first_response})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Here are the search results:\n\n{search_results}\n\n"
                f"Now answer the original question: {task}\n"
                "Base your answer only on these results. If they don't fully "
                "answer it, say what's still uncertain rather than guessing."
            ),
        }
    )
    final_answer = call_model(messages).strip()
    print("Final answer:")
    print(final_answer)


if __name__ == "__main__":
    answer_with_search("What is the current recommended way to validate file uploads in Node.js?")