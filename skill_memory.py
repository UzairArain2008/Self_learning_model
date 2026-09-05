"""
Structured memory for learned skills.

Design choices, deliberately minimal:
- JSONL (one JSON object per line), not a database. At this scale (an
  experiment, not a product with concurrent users) a database is more
  machinery than the problem needs — appending a line is enough, and
  it's trivially inspectable by just opening the file.
- Every record carries its confidence/verification status as an
  explicit field, not something inferred later. This is the fix from
  Round 7 applied one layer up: don't make anything — model or future
  code — responsible for "remembering" that a skill was unverified.
"""

import json
import hashlib
import datetime
from pathlib import Path

SKILLS_FILE = Path("skills.jsonl")


def _make_skill_id(query: str) -> str:
    # Short deterministic id so the same query re-learned later can be
    # recognized as a duplicate/update rather than an unrelated new skill.
    return hashlib.sha256(query.encode()).hexdigest()[:12]


def save_skill(
    query: str,
    answer: str,
    source_urls: list[str],
    best_tier: int,
    code: str | None,
    syntax_passed: bool | None,
    syntax_message: str | None,
) -> dict:
    """Appends one skill record and returns it (so callers can log/print it)."""
    record = {
        "skill_id": _make_skill_id(query),
        "query": query,
        "answer": answer,
        "source_urls": source_urls,
        "source_tier": best_tier,  # 1 = official docs, 3 = unverified blog/forum
        "code": code,
        "syntax_passed": syntax_passed,  # None if no code was present to check
        "syntax_message": syntax_message,
        "confidence": _compute_confidence(best_tier, syntax_passed),
        "learned_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    with SKILLS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def _compute_confidence(best_tier: int, syntax_passed: bool | None) -> str:
    """
    Single source of truth for what 'confidence' means, so nothing else
    in the system has to re-derive or remember this logic separately.
    """
    if syntax_passed is False:
        return "failed"  # never call this verified, regardless of source tier
    if best_tier == 1 and syntax_passed in (True, None):
        return "verified"
    if best_tier <= 2:
        return "likely"
    return "unverified"


def load_skills() -> list[dict]:
    if not SKILLS_FILE.exists():
        return []
    with SKILLS_FILE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def find_existing_skill(query: str) -> dict | None:
    """Check if we already learned something for this exact query, so the
    pipeline can skip re-searching (and re-spending search-API calls) for
    a duplicate request."""
    skill_id = _make_skill_id(query)
    for record in load_skills():
        if record["skill_id"] == skill_id:
            return record
    return None