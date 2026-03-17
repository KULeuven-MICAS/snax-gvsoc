"""
Pytest tests that run pyright to verify Config's dataclass_transform type annotations.

Uses two fixture files:
- typecheck/valid_usage.py  — must produce 0 pyright errors
- typecheck/invalid_usage.py — must produce exactly the errors annotated with # E:

Pyright is the same engine Pylance (VS Code) uses for type checking and hover info.
"""

import json
import re
import subprocess
from pathlib import Path


TYPECHECK_DIR = Path(__file__).parent / 'typecheck'
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _run_pyright(path: Path) -> dict:
    result = subprocess.run(
        ['pyright', '--outputjson', str(path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return json.loads(result.stdout)


class TestPyrightValidUsage:
    """Valid Config usage must produce zero pyright errors."""

    def test_no_errors(self):
        data = _run_pyright(TYPECHECK_DIR / 'valid_usage.py')
        errors = [
            f"L{d['range']['start']['line'] + 1}: {d['message']}"
            for d in data['generalDiagnostics']
            if d['severity'] == 'error'
        ]
        assert errors == [], "Unexpected pyright errors in valid_usage.py:\n" + "\n".join(errors)


class TestPyrightInvalidUsage:
    """
    Each line in invalid_usage.py marked with # E: must produce a pyright error
    whose message contains the annotated substring.
    """

    def _expected_errors(self) -> list[tuple[int, str]]:
        """Parse # E: annotations from invalid_usage.py into (line_number, expected_snippet) pairs."""
        src = (TYPECHECK_DIR / 'invalid_usage.py').read_text()
        result = []
        for lineno, line in enumerate(src.splitlines(), start=1):
            # Only match inline annotations that appear after a closing paren
            # (i.e., after an actual function call), not in docstrings or comments
            m = re.search(r'\).*#\s*E:\s*(.+)', line)
            if m:
                result.append((lineno, m.group(1).strip()))
        return result

    def test_error_count_matches_annotations(self):
        data = _run_pyright(TYPECHECK_DIR / 'invalid_usage.py')
        actual_errors = [d for d in data['generalDiagnostics'] if d['severity'] == 'error']
        expected = self._expected_errors()
        assert len(actual_errors) == len(expected), (
            f"Expected {len(expected)} errors, got {len(actual_errors)}.\n"
            f"Actual: {[d['message'] for d in actual_errors]}"
        )

    def test_each_annotated_line_has_matching_error(self):
        data = _run_pyright(TYPECHECK_DIR / 'invalid_usage.py')
        actual_by_line: dict[int, str] = {
            d['range']['start']['line'] + 1: d['message']
            for d in data['generalDiagnostics']
            if d['severity'] == 'error'
        }
        for lineno, snippet in self._expected_errors():
            assert lineno in actual_by_line, f"Expected error on line {lineno} not found"
            assert snippet in actual_by_line[lineno], (
                f"Line {lineno}: expected message to contain:\n  {snippet!r}\n"
                f"Got:\n  {actual_by_line[lineno]!r}"
            )
