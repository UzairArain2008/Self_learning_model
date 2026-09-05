"""
Step 4 — Sandboxed syntax check on generated code (phase 1 verification).

Scope, honestly: this checks the code PARSES, not that it's behaviorally
correct (e.g. it won't catch "multer config missing fileFilter" — that's
a semantic gap, not a syntax error). This is the cheapest, first-value
check in the verification ladder: use the platform's native syntax
checker instead of writing one. Deeper behavioral testing (running it
against real inputs) is a later step once this baseline works.

Requires: Node.js installed and on PATH (node --version to confirm).
Run: python 04_sandbox_check.py
"""

import re
import subprocess
import tempfile
import os

CODE_BLOCK_PATTERN = re.compile(r"```(?:javascript|js)?\n(.*?)```", re.DOTALL)


def extract_code(answer_text: str) -> str | None:
    match = CODE_BLOCK_PATTERN.search(answer_text)
    return match.group(1).strip() if match else None


def check_syntax(code: str, timeout_seconds: int = 5) -> tuple[bool, str]:
    """
    Runs `node --check` on the code in an isolated temp file.
    Returns (passed, message). Does NOT execute the code — --check only
    parses it, so this is safe even if the code would otherwise do
    something unwanted (no network/filesystem access happens here).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode == 0:
            return True, "Syntax OK"
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "node not found — install Node.js and ensure it's on PATH"
    except subprocess.TimeoutExpired:
        return False, f"Syntax check timed out after {timeout_seconds}s (unexpected for --check)"
    finally:
        os.unlink(tmp_path)  # clean up regardless of outcome


if __name__ == "__main__":
    # Paste in the code block the model produced, for a standalone test
    # before wiring this into the full search->answer->verify pipeline.
    example_answer = """
Here's the middleware:

```javascript
const multer = require('multer');

const upload = multer({
  limits: {
    fileSize: 1024 * 1024 * 10,
  },
});

module.exports = upload;
```
"""
    code = extract_code(example_answer)
    if code is None:
        print("No code block found in answer — nothing to check.")
    else:
        passed, message = check_syntax(code)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {message}")
        if not passed:
            print("A skill whose code fails even a syntax check should never be stored as verified.")