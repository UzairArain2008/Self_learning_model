Experimenting on self learning model after training Right now using Qwen2.5-1.5B-Instruct-q4_k_m as of my hardware limit plus it's good for this experimentation

02_test_tool.py --- this file is to test is model would be able to make a on internet to learn something on users command I didn't provide the direct access to internet but it's fake internet so but we failed as model didn't call the inertent yest it answers our questions as it's not dumb though so we gonna run the diagnose it 

Ran 02b_diagnose.py to isolate the cause. Two findings:

1. /props confirmed the active chat template DOES include tool-call
   formatting (found 'tool_call', 'tools', '<tool_call>' markers) —
   ruled out "template doesn't support tools" as the cause.

2. Forcing tool_choice="required" hung/timed out even at 300s.
   Root cause (confirmed via search, not just guessing): llama.cpp's
   grammar-constrained decoding is known to be unreliable/slow with
   Qwen2.5's default tool-call template when tool_choice is forced —
   documented issue in the llama.cpp ecosystem, not a bug in our setup.
   Decision: drop tool_choice="required" as a path entirely — the real
   system will use "auto" anyway, so this was a detour, not a
   requirement.

Root cause of the original 0/5: template works, but the model wasn't
choosing to call the tool on its own under tool_choice="auto" — a
prompt-strength problem, not a template/server problem.

Next fix being tested: (1) stronger system prompt explicitly forbidding
answering from memory, (2) one-shot example showing the exact tool-call
pattern in-context. Small models follow demonstrated patterns more
reliably than described rules — testing whether that closes the gap.

## Round 2 — stronger prompt still 0/5, but new signal found

Added a one-shot example + a much stricter system prompt forbidding
answering from memory. Still 0/5 structured tool calls — but trial 2
was revealing: the model responded "I would need to search the web
for the most recent and accurate information" — i.e. it VERBALLY
recognized it should search, but didn't trigger the tool mechanism.

This changes the hypothesis. Instead of "model won't use tools,"
now testing: "model IS attempting to call the tool, but is writing
it as plain text (e.g. <tool_call>...</tool_call> inside content)
rather than through llama.cpp's structured tool_calls field."

This is a known category of bug — llama.cpp not correctly parsing
Qwen2.5's tool-call text format into the API's structured field,
independent of the model's own behavior.

Patched the test script to detect this case explicitly (checking
raw content for tool_call markers) instead of only checking the
structured field. Re-running to confirm.

## Round 3 — ruled out parser bug, pivoting to text protocol

Re-ran with content-inspection added: 0/5 again, and this time NO
tool_call markers appeared in raw text either (previous run had shown
the model verbally acknowledging it should search). Rules out the
"llama.cpp isn't parsing a text-form tool call" hypothesis from Round 2.

New evidence found: llama.cpp's own documentation only lists native
tool-calling as verified starting at Qwen2.5-7B, not 1.5B. Combined with
0/5 across two different prompting strategies, working hypothesis is
now: this may be a genuine capability ceiling at 1.5B for spontaneous
structured tool-use decisions, not a fixable prompt/config issue.

Decision: instead of continuing to force OpenAI-style JSON function
calling (a schema-conformance task), pivoted to the simplest possible
alternative — a one-line plain-text convention ("SEARCH: <query>")
parsed manually in Python, bypassing llama.cpp's tool-call machinery
entirely. Rationale: this is a much easier pattern for a small model
to learn than JSON-schema adherence, and removes an entire layer
(the tool-call parser) as a source of failure.

If this still fails, next step is testing the identical protocol
against a larger model (7B class) to confirm whether this is a model
size ceiling or a technique problem — an important distinction for
deciding whether 1.5B is viable for the agent role at all.

## Round 4 — text protocol confirmed reliable (5/5), wiring real search

03_real_search.py hit 5/5 — the simple "SEARCH: <query>" convention
works reliably where full OpenAI-style JSON tool-calling did not.
Conclusion: 1.5B can make the right decision (search vs. answer), it
just can't reliably conform to a JSON function-calling schema. Simpler
protocol, same underlying capability, no size upgrade needed for this
step.

Wired in a real search API (Tavily — built for LLM/agent use, clean
result format, free tier). Loop is now: model emits SEARCH line →
real Tavily call → results fed back as next turn → model answers
grounded in retrieved content instead of memory.

Not yet added: trust-tiering of returned sources (official docs vs.
random blog) or staleness checking — next step once this baseline
round-trip is confirmed working end to end.

## Round 5 — added trust-tiering after catching a real bad-lesson example

Round 4's live test exposed the exact failure mode this project is
about: all 3 search results were unverified blogs (DEV.to, Medium,
a personal blog), and the synthesized answer had a real security gap
— it recommended validating uploads via file extension and
client-supplied MIME type, both of which are trivially spoofable by
an attacker. No official/authoritative source was among the results,
and nothing in the pipeline flagged that.

Added trust-tiering to 03_real_search.py: domains classified as
Tier 1 (official docs — nodejs.org, OWASP, MDN, etc.), Tier 2
(established publications), or Tier 3 (everything else, default).
The model is now told explicitly when all sources are Tier 3, and
instructed to caveat its answer as provisional rather than confident
in that case.

Next: re-run with the same test question and confirm the model
actually changes its confidence framing when sources are low-tier,
not just that the tier label gets computed correctly.

## Round 6 — moved API key to .env, added .gitignore

Since this repo is public, hardcoding or manually exporting the API
key each session was a real risk of accidental leakage. Switched to
python-dotenv: real key lives in a local .env (gitignored, never
committed), .env.example documents the required variable without a
real value. Script now fails with a clear error if the key is
missing, instead of a raw KeyError.

## Round 7 — stopped trusting the model to self-caveat

Added an instruction telling the model to caveat its answer when all
sources were Tier 3. Model ignored it and answered with full confidence
anyway (search results were Reddit/Medium/a blog — genuinely Tier 3,
correctly classified — but the "you MUST caveat" instruction, buried
in a long user turn, didn't change its output).

Fix: stopped asking the model to remember this at all. Since the tier
is already computed objectively in Python, the disclaimer is now
prepended in code whenever best_tier == 3 — not dependent on model
instruction-following.

General pattern worth keeping for the rest of this project: anything
we can already determine objectively (source tier, test pass/fail,
staleness by date) should be enforced in code, not left as a prompted
instruction to a small model. Reserve prompting for genuine judgment
calls where no objective check exists.

## Round 8 — added a native syntax check, found a second bad-lesson example

Noticed the multer example from the last run has no `fileFilter` —
meaning it doesn't actually validate file type despite claiming to.
Different failure mode than trust-tiering catches: this isn't about
source credibility, it's about the generated code being wrong/
incomplete regardless of source.

Added 04_sandbox_check.py: extracts the code block from a model's
answer and runs `node --check` on it in an isolated temp file —
parses only, doesn't execute, so it's safe even on untrusted
generated code. This is the cheapest possible verification step
(native tool, no custom parser) and catches syntax-level hallucinations
before they'd ever be stored as a "verified" skill.

Scoped honestly: this only catches syntax errors, not semantic ones
like the missing fileFilter — that needs actual behavioral testing
against real inputs, which is a bigger step for later. Syntax check
is the cheap first filter; not a full solve.

Next: wire this into the real search->answer pipeline, and decide
whether a failed check should just flag the answer or trigger an
automatic retry with the error fed back to the model.

## Round 9 — full 8-question comparison run: naive vs. verified

Ran the fixed 8-question test set through both pipelines.

RESULT: 6/8 questions had a true source tier of 3 (search results were
entirely unverified blogs/forums). The naive pipeline stored all 6 as
confidence="trusted" with zero indication of low source quality. The
verified pipeline correctly flagged 5/6 of these as "unverified"
(6th caused a bug — see below).

Headline number for the writeup: naive pipeline confidently mislabeled
6/8 answers; verified pipeline caught 5/6 of them.

Two new findings from this run, not previously seen:

1. CONTENT CONTAMINATION: on 2 questions (CORS, rate limiting), a
   Tier 1 (official docs) source was found, earning confidence=
   "verified" — but the actual answer text traced back to a Tier 3
   source shown alongside it, not the official doc. Honest limitation:
   the current tier system checks "was a good source present," not
   "did the model actually rely on the good source." Worth stating
   explicitly in the final writeup as a known gap, not hidden.

2. BUG: on one question, the model's second response (after seeing
   search results) was itself another "SEARCH: ..." line — a second
   search attempt the pipeline doesn't support. This got stored
   verbatim as if it were a real (if unverified) answer. Fixed by
   detecting a second SEARCH: pattern and refusing to save it as a
   skill at all, rather than mislabeling failed generation as a
   low-confidence answer.

Also compared JWT storage question specifically: naive answer states
"encrypt JWT using bcrypt" — bcrypt is a one-way hash, not reversible
encryption, so this advice doesn't actually work as described. A
concrete example of confidently-wrong naive output, useful for the
writeup's qualitative examples section alongside the file-upload case.

## Round 10 — clean final comparison, bug fix confirmed

Cleared skills.jsonl and re-ran both pipelines on the fixed 8-question
set.

Verified pipeline: 7/8 questions produced a saved answer (the 8th
correctly triggered the Round 9 bug fix — model tried to search again
instead of answering, and the pipeline refused to save it rather than
storing garbage with a confidence label). Of the 7 saved: 6 were
Tier 3 sources, all correctly flagged "unverified"; 1 was Tier 2,
flagged "likely". 0 mislabeled.

Naive baseline: 8/8 saved as confidence="trusted" — no differentiation
by source quality at all, including the 6 answers sourced entirely
from blogs/forums.

RESULT: verified pipeline correctly differentiated trust level on
7/7 saved answers; naive pipeline differentiated on 0/8. This is the
core comparison result for the writeup.

CAVEAT (important, stating honestly): re-running the same CORS and
rate-limiting queries across two separate sessions returned different
source tiers each time (Tier 1 docs found in run 1, Tier 3 only in
run 2) — live web search isn't fully reproducible run-to-run. This
comparison demonstrates the mechanism working correctly on the inputs
it received, not a fully controlled repeatable experiment. Noting this
explicitly rather than presenting the numbers as more rigorous than
they are.

This closes the core verification-loop comparison phase.