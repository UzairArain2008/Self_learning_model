# Self-Learning Model — Search, Verify, Remember

A small experiment testing one question: **does adding a lightweight
verification loop (source trust-tiering + syntax checking) to a
self-teaching local agent actually reduce confidently-wrong answers,
compared to an agent that just trusts whatever it finds?**

Runs entirely on a 1.5B model (Qwen2.5-1.5B-Instruct, quantized) via
llama.cpp — no GPU required.

## Result

Ran the same 8 real-world dev questions through two versions of the same
pipeline:

- **Naive** — searches the web, answers, stores every answer as
  `confidence: "trusted"`, regardless of where it came from.
- **Verified** — same search, but classifies sources by trust tier
  (official docs vs. random blog), syntax-checks any generated code, and
  stores an honest confidence label based on both.

| | Naive | Verified |
|---|---|---|
| Answers that got a "trusted"/high-confidence label despite being sourced entirely from unverified blogs | 6/6 | 0/6 |
| Answers where confidence correctly reflected source quality | 0/8 | 7/7 saved |

The naive pipeline gave every answer the same confidence label no matter
what it was based on. The verified pipeline correctly told the
difference. That's the core finding — full details, including two honest
limitations discovered along the way, are in [REPORT.md](REPORT.md).

## How it works

1. Model decides whether it needs to search (a simple `SEARCH: <query>`
   text convention — see REPORT.md for why we didn't use standard
   JSON tool-calling).
2. Real web search via Tavily.
3. Sources classified into trust tiers (official docs > established
   publications > everything else).
4. Any generated code gets a native syntax check (`node --check`).
5. Answer + confidence label saved to a structured memory file
   (`skills.jsonl`) — never re-searched for the same question twice.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # add your Tavily API key
llama-server -m Qwen2.5-1.5B-Instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 --jinja
python 03_real_search.py       # verified pipeline
python naive_baseline.py       # naive baseline, for comparison
```

## Why no fine-tuning (yet)

This project deliberately keeps the model's weights frozen. Everything
it "learns" lives in an external, inspectable memory file — not baked
into parameters. That's a design choice, not a shortcut:

- **Auditability** — a bad learned "skill" is one line in a JSON file
  you can read and delete. A bad weight update is smeared across the
  network with no clean way to isolate or undo it.
- **No catastrophic forgetting risk** — updating weights live risks
  silently degrading unrelated skills the model already had. External
  memory can't do that; it's just a lookup.
- **Rollback is free** — deleting a bad memory record is instant. Live
  weight updates need checkpointing to be undoable at all, at which
  point you've reinvented offline fine-tuning anyway.

Real fine-tuning is planned as a *later, separate phase* — periodically
batching verified skills into a QLoRA fine-tune run (on rented/free-tier
GPU compute), gated behind a regression test suite before any new
checkpoint replaces the running model. Not done yet because it needs GPU
access this phase didn't require, and because validating the
verification loop first (this repo) was the cheaper, faster thing to
get right before spending compute on it.

## Known limitations

- Trust-tiering checks whether a good source *was found*, not whether
  the model's answer actually *relied on it* — an answer can earn a high
  confidence label while still pulling specifics from a lower-tier
  source shown alongside a good one.
- Syntax checking catches malformed code, not semantically wrong code
  (e.g. a validator missing a security check can still pass).
- Live web search isn't perfectly reproducible between runs, so this is
  an illustrative comparison, not a fully controlled experiment.

## License

MIT — see [LICENSE](LICENSE).

## Full development log

See [REPORT.md](REPORT.md) for the complete round-by-round debugging
history, including dead ends.