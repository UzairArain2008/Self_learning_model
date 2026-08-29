"""
Step 2 — Confirm the model can reliably call tools in a parseable format.

This does NOT hit the real internet yet. The "search" tool below is fake —
it just returns a canned result — because the only thing we're testing here
is: does the model correctly decide to call a tool, and does it format the
call so we can parse it? That's a model/prompt-format question, separate
from "does search work," so we isolate it first.

Run: python 02_test_tools.py
Requires: pip install requests
"""

import json
import requests

LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"

# Minimal tool schema, OpenAI-style function calling format.
# Qwen2.5-Instruct was trained on this format, so llama-server (with --jinja)
# should translate it into the model's native tool-call template.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information on a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def fake_web_search(query: str) -> str:
    """Stand-in for a real search call — step 3 replaces this."""
    return f"[FAKE RESULT] Top result for '{query}': example.com/some-doc"


def call_model(messages: list) -> dict:
    resp = requests.post(
        LLAMA_SERVER_URL,
        json={
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.2,  # low temp: we want consistent, parseable output, not creativity
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def run_test(task: str, n_trials: int = 5):
    """
    Ask the model to do something that clearly requires a tool call,
    n_trials times, and report how often it actually produces a valid,
    parseable tool call vs. just answering in plain text (which would
    mean it's hallucinating an answer instead of looking it up — bad
    for an agent that's supposed to verify things before trusting them).
    """
    successes = 0
    for i in range(n_trials):
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an assistant that must use the web_search tool "
                    "to look up anything you're not certain about. Do not "
                    "guess or answer from memory for factual lookups."
                ),
            },
            {"role": "user", "content": task},
        ]
        result = call_model(messages)
        choice = result["choices"][0]["message"]

        tool_calls = choice.get("tool_calls")
        if tool_calls:
            successes += 1
            call = tool_calls[0]["function"]
            print(f"[trial {i+1}] OK — called {call['name']} with args: {call['arguments']}")
            # Sanity-check the arguments actually parse as JSON
            try:
                json.loads(call["arguments"])
            except json.JSONDecodeError:
                print(f"  WARNING: arguments not valid JSON: {call['arguments']!r}")
                successes -= 1
        else:
            print(f"[trial {i+1}] FAIL — no tool call, model just answered:")
            print(f"  {choice.get('content', '')[:200]}")

    print(f"\n{successes}/{n_trials} trials produced a valid, parseable tool call.")
    if successes < n_trials:
        print(
            "Below 100%: before building real tools on top of this, worth "
            "tightening the system prompt or trying a slightly higher/lower "
            "temperature — an unreliable tool-call format will silently "
            "break the verification loop later (a 'search' that never "
            "happened looks identical to a search that did, from memory's "
            "point of view)."
        )


if __name__ == "__main__":
    run_test("What is the current recommended way to validate file uploads in Node.js?")