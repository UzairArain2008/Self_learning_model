"""
Shared verification helpers — code extraction and syntax checking.
Imported by both 04_sandbox_check.py (standalone test) and
03_real_search.py (real pipeline), so the logic lives in one place.
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
    Runs `node --check` on the code in an isolated temp file. Parses only,
    does not execute — safe even on untrusted generated code.
    Returns (passed, message).
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
        os.unlink(tmp_path)