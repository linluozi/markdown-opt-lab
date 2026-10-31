"""Run every differential case with the markdown package at MD_TREE and
print a JSON mapping case_id -> sha256(rendered HTML) on stdout.

Used by tests/test_diff.py; the comparison is on the exact rendered bytes,
so any semantic difference between baseline and optimized shows up as a
hash mismatch.
"""
import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "benchmark"))
sys.path.insert(0, os.environ["MD_TREE"])

import cases  # noqa: E402
import markdown  # noqa: E402


def main():
    assert os.path.abspath(markdown.__file__).startswith(
        os.path.abspath(os.environ["MD_TREE"])), markdown.__file__
    out = {}
    for case_id, text in cases.iter_cases():
        html = markdown.markdown(text, extensions=["markdown.extensions.abbr"])
        out[case_id] = hashlib.sha256(html.encode("utf-8")).hexdigest()
    json.dump(out, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
