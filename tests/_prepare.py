"""Applies patch.diff to a copy of the upstream tree and returns its path."""
import os
import shutil
import subprocess
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def upstream_tree():
    """Path to a pristine Python-Markdown checkout (env MD_UPSTREAM or
    /tmp/md-upstream; cloned over SSH if absent)."""
    path = os.environ.get("MD_UPSTREAM", "/tmp/md-upstream")
    if not os.path.isdir(os.path.join(path, "markdown")):
        subprocess.run(
            ["git", "clone", "--depth=1",
             "git@github-linluozi:Python-Markdown/markdown.git", path],
            check=True)
    return path


def optimized_tree():
    """Copy the upstream tree and apply patch.diff to it (cached in /tmp)."""
    src = upstream_tree()
    dst = tempfile.mkdtemp(prefix="md-opt-tests-")
    shutil.copytree(src, dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(
                        ".git", "__pycache__", "*.pyc"))
    subprocess.run(
        ["git", "apply", "-p1", os.path.join(REPO_ROOT, "patch.diff")],
        cwd=dst, check=True)
    return dst
