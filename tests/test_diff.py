"""Differential test: baseline vs patched `abbr` block processor.

Every case from benchmark/cases.py is rendered by the pristine upstream
checkout and by the patched one; the SHA-256 of the exact rendered HTML
must match for all of them (>= 2400 cases, including empty input, single
definitions, invalid/empty definitions, regex metacharacters, CRLF,
non-ASCII, 5000-char titles and 50/300/400-definition runs).

Run:  python3 -m pytest tests/test_diff.py -q -s
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _prepare  # noqa: E402

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_hash_runner.py")
MIN_CASES = 2000


def _hashes(tree):
    env = dict(os.environ, MD_TREE=tree)
    proc = subprocess.run([sys.executable, RUNNER], env=env,
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def test_diff_byte_identical():
    baseline = _hashes(_prepare.upstream_tree())
    optimized = _hashes(_prepare.optimized_tree())
    assert len(baseline) == len(optimized) >= MIN_CASES, (
        len(baseline), len(optimized))
    diffs = [k for k in baseline if baseline[k] != optimized.get(k)]
    assert not diffs, f"{len(diffs)} differing cases, first: {diffs[:5]}"
    print(f"\ndifferential cases: {len(baseline)}, differences: 0")


def test_optimized_is_deterministic():
    first = _hashes(_prepare.optimized_tree())
    second = _hashes(_prepare.optimized_tree())
    assert first == second
    print(f"determinism re-run: {len(first)} cases, 0 differences")
