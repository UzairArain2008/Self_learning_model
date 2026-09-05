# Development Log

Full round-by-round research diary for this experiment. See [README.md](README.md)
for the project summary and results — this file is the detailed trace of how
we got there, kept for transparency and for anyone curious about the actual
debugging process (including the dead ends).

---

Experimenting on self learning model after training. Right now using
Qwen2.5-1.5B-Instruct-q4_k_m as of hardware limits — plus it's a good fit
for this experimentation.

02_test_tools.py — this file tests whether the model can decide to search
the internet to learn something on the user's command. No direct internet
access provided yet (fake internet), but even that failed — the model
didn't call the tool, it just answered our questions directly. Not dumb,
just not using tools — so we ran the diagnose script.

Ran 02b_diagnose.py to isolate the cause. Two findings:

1. `/props` confirmed the active chat template DOES include tool-call
   formatting (found 'tool_call', 'tools', '<tool_call>' markers) —
   ruled out "template doesn't support tools" as the cause.

2. Forcing `tool_choice="required"` hung/timed out even at 300s.
   Root cause (confirmed via search, not just guessing): llama.cpp's
   grammar-constrained decoding is known to be unreliable/slow with
   Qwen2.5's default tool-call template when tool_choice is forced —
   documented issue in the llama.cpp ecosystem, not a bug in our setup.
   Decision: drop `tool_choice="required"` as a path entirely — the real
   system will use "auto" anyway, so this was a detour, not a
   requirement.

Root cause of the original 0/5: template works, but the model wasn't
choosing to call the tool on its own under `tool_choice="auto"` — a
prompt-strength problem, not a template/server problem.

## Round 2 — stronger prompt still 0/5, but new signal found

Added a one-shot example + a much stricter system prompt forbidding
answering from memory. Still 0/5 structured tool calls — but trial 2
was revealing: the model responded "I would need to search the web for
the most recent and accurate information" — i.e. it verbally recognized
it should search, but didn't trigger the tool mechanism.

New hypothesis: model IS attempting to call the tool, but writing it as
plain text (e.g. `<tool_call>...</tool_call>` inside content) rather than
through llama.cpp's structured `tool_calls` field.

## Round 3 — ruled out parser bug, pivoting to text protocol

Re-ran with content-inspection added: 0/5 again, no tool_call markers in
raw text either. Rules out the "parser isn't extracting a text-form tool
call" hypothesis from Round 2.

New evidence: llama.cpp's own docs only list native tool-calling as
verified starting at Qwen2.5-7B, not 1.5B. Working hypothesis: this may
be a genuine capability ceiling at 1.5B for spontaneous structured
tool-use decisions, not a fixable prompt/config issue.

Decision: pivot to the simplest possible alternative — a one-line plain
text convention (`SEARCH: <query>`) parsed manually in Python, bypassing
llama.cpp's tool-call machinery entirely.

## Round 4 — text protocol confirmed reliable (5/5), wiring real search

`02c_text_protocol.py` hit 5/5 — the simple `SEARCH: <query>` convention
works reliably where full OpenAI-style JSON tool-calling did not.
Conclusion: 1.5B can make the right decision (search vs. answer), it just
can't reliably conform to a JSON function-calling schema.

Wired in a real search API (Tavily). Loop is now: model emits SEARCH line
→ real Tavily call → results fed back as next turn → model answers
grounded in retrieved content instead of memory.

## Round 5 — added trust-tiering after catching a real bad-lesson example

Round 4's live test exposed the exact failure mode this project is about:
all 3 search results were unverified blogs, and the synthesized answer had
a real security gap — validating uploads via file extension and
client-supplied MIME type, both trivially spoofable.

Added trust-tiering: domains classified as Tier 1 (official docs), Tier 2
(established publications), or Tier 3 (everything else, default).

## Round 6 — moved API key to .env, added .gitignore

Since this repo is public, hardcoded/manually-exported keys were a real
leak risk. Switched to python-dotenv: real key lives in a local `.env`
(gitignored, never committed), `.env.example` documents the required
variable without a real value.

## Round 7 — stopped trusting the model to self-caveat

Told the model to caveat its answer when all sources were Tier 3. It
ignored the instruction and answered with full confidence anyway.

Fix: stopped asking the model to remember this at all. Since the tier is
already computed objectively in Python, the disclaimer is now prepended
in code whenever `best_tier == 3` — not dependent on model
instruction-following. **General pattern kept for the rest of the
project: anything determinable objectively (source tier, test pass/fail)
is enforced in code, not left as a prompted instruction to a small
model.**

## Round 8 — added a native syntax check, found a second bad-lesson example

Noticed the multer example from Round 5 has no `fileFilter` — it doesn't
actually validate file type despite claiming to. A different failure
mode than trust-tiering catches: wrong/incomplete code, regardless of
source.

Added `04_sandbox_check.py`: extracts the code block from an answer and
runs `node --check` on it in an isolated temp file — parses only,
doesn't execute. Cheapest possible verification step; scoped honestly as
syntax-only, not semantic (doesn't catch the missing-fileFilter class of
bug).

## Round 9 — full 8-question comparison run: naive vs. verified

Ran a fixed 8-question test set through both pipelines.

**Result:** 6/8 questions had a true source tier of 3 (unverified
blogs/forums). The naive pipeline stored all 6 as `confidence="trusted"`
with zero indication of low source quality. The verified pipeline
correctly flagged 5/6 of these as `unverified` (the 6th hit a bug — see
below).

Two new findings:

1. **Content contamination** — on 2 questions, a Tier 1 source was found
   (earning `confidence="verified"`), but the actual answer text traced
   back to a Tier 3 source shown alongside it, not the official doc.
   Honest limitation: the tier system checks "was a good source
   present," not "did the model rely on the good source."

2. **Bug** — on one question, the model's second response was itself
   another `SEARCH: ...` line (a second search attempt the pipeline
   didn't support), and this got stored verbatim as if it were a real
   answer. Fixed by detecting a second SEARCH pattern and refusing to
   save it as a skill.

## Round 10 — clean final comparison, bug fix confirmed

Cleared the skill store and re-ran both pipelines on the fixed 8-question
set.

**Verified pipeline:** 7/8 questions produced a saved answer (the 8th
correctly triggered the Round 9 fix instead of storing garbage). Of the
7 saved: 6 were Tier 3, all correctly flagged `unverified`; 1 was Tier 2,
flagged `likely`. 0 mislabeled.

**Naive baseline:** 8/8 saved as `confidence="trusted"` — no
differentiation by source quality at all.

**Result:** verified pipeline correctly differentiated trust level on
7/7 saved answers; naive pipeline differentiated on 0/8.

**Caveat, stated honestly:** re-running the same queries across separate
sessions returned different source tiers each time (live web search
isn't fully reproducible run-to-run). This demonstrates the mechanism
working correctly on the inputs it received, not a fully controlled
repeatable experiment.