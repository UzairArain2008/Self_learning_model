"""
Step 4 — Standalone test of the shared verification module.
Run: python 04_sandbox_check.py
"""

from verification import extract_code, check_syntax

if __name__ == "__main__":
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