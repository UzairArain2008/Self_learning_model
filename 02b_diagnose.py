"""
Step 2b — Diagnose why 0/5 tool calls happened.

Run: python 02b_diagnose.py

This checks two things separately:
1. Does the server's active chat template even mention tool-call formatting?
   (If not, the model literally never saw the tools — this is a template/
   server-config problem, not a model or prompt problem.)
2. If we FORCE tool_choice="required" instead of "auto", does the model
   comply? If it still answers in plain text even when forced, that
   confirms the template isn't wired up. If it complies when forced,
   the template works but the model just isn't choosing to use it on
   its own — a different, easier problem to fix (prompt/temperature).
"""

import json
import requests

LLAMA_SERVER_URL_BASE = "http://127.0.0.1:8080"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information on a topic.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]


def check_template():
    print("=== Checking active chat template (/props) ===")
    try:
        resp = requests.get(f"{LLAMA_SERVER_URL_BASE}/props", timeout=10)
        resp.raise_for_status()
        props = resp.json()
        template = props.get("chat_template", "")
        print(f"Template length: {len(template)} chars")
        markers = ["tool_call", "tools", "<tool_call>", "function_call"]
        found = [m for m in markers if m in template]
        if found:
            print(f"Template DOES reference tool-calling (found: {found}) — template is likely fine.")
        else:
            print(
                "Template does NOT appear to reference tool-calling at all.\n"
                "This strongly suggests the GGUF's embedded template lacks "
                "tool-call support, or --jinja wasn't applied.\n"
                "Fix: re-download a Qwen2.5-1.5B-Instruct GGUF from a source "
                "that embeds the tool-use chat template (check the model "
                "card on Hugging Face for 'tool calling' / 'function calling' "
                "support), and confirm --jinja is in your server launch command."
            )
    except requests.exceptions.RequestException as e:
        print(f"Couldn't reach /props: {e}")
        print("(Older llama.cpp builds may not expose /props — not fatal, skip to forced test below.)")


def check_forced_tool_choice():
    print("\n=== Forcing tool_choice='required' ===")
    resp = requests.post(
        f"{LLAMA_SERVER_URL_BASE}/v1/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "What is the current recommended way to validate file uploads in Node.js?"}
            ],
            "tools": TOOLS,
            "tool_choice": "required",
            "temperature": 0.2,
        },
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    print(json.dumps(result, indent=2)[:1500])  # raw response, truncated

    choice = result["choices"][0]["message"]
    if choice.get("tool_calls"):
        print(
            "\n-> Model DID call the tool when forced. Template works. "
            "The issue is just that it wasn't choosing to use tools on its "
            "own with tool_choice='auto' — that's fixable with a stronger "
            "system prompt, not a server/template fix."
        )
    else:
        print(
            "\n-> Model still did NOT call the tool even when forced. "
            "This confirms the template/server isn't passing tool "
            "definitions to the model at all — fix the template/server "
            "setup before touching the prompt."
        )


if __name__ == "__main__":
    check_template()
    check_forced_tool_choice()