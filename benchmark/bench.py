#!/usr/bin/env python3
"""Benchmark harness for the Python-Markdown `abbr` block-processor fix.

The benchmark imports a pristine upstream checkout (``--upstream``) or a
patched copy of it (``--patched``, applies ``patch.diff`` to a temp copy),
runs ``markdown.markdown(doc, extensions=['markdown.extensions.abbr'])`` on
three document sizes, and records every timed sample to ``benchmark/raw/``.

Timing uses ``time.perf_counter()``. The generator is seeded
(``benchmark/cases.py`` -> ``SEED``), each size gets WARMUP untimed calls and
SAMPLES timed calls, and the report keeps the raw seconds plus
median/p25/p75.

Usage:
    python3 benchmark/bench.py --upstream /tmp/md-upstream --impl baseline
    python3 benchmark/bench.py --upstream /tmp/md-upstream --impl optimized --patched
"""
import argparse
import hashlib
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(REPO_ROOT, "benchmark", "raw")
SEED = 20261101
EXT = "markdown.extensions.abbr"
WARMUP = 3
SAMPLES = 5
SCALES = [("small", 150), ("medium", 600), ("large", 2400)]


def build_doc(n_defs):
    """A document whose first block is n_defs consecutive abbreviation
    definitions, followed by prose that uses them."""
    lines = [f"*[AB{i}]: abbreviated term number {i}" for i in range(n_defs)]
    used = [f"AB{i}" for i in range(0, max(n_defs, 1), 7)]
    body = ["", "# Abbreviations", "", " ".join(used) + " appear in prose.", ""]
    return "\n".join(lines) + "\n" + "\n".join(body)


def percentiles(xs):
    xs = sorted(xs)
    n = len(xs)

    def q(p):
        idx = (n - 1) * p
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        return xs[lo] + (xs[hi] - xs[lo]) * (idx - lo)

    return q(0.25), q(0.5), q(0.75)


def cpu_model():
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def mem_total_kb():
    with open("/proc/meminfo") as fh:
        for line in fh:
            if line.startswith("MemTotal"):
                return int(line.split()[1])
    return -1


def prepare_optimized(upstream):
    dst = os.path.join(tempfile.gettempdir(), "md-opt-bench-tree")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(upstream, dst, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc"))
    patch = os.path.join(REPO_ROOT, "patch.diff")
    subprocess.run(["git", "apply", "-p1", patch], cwd=dst, check=True)
    return dst


def load_markdown(tree):
    sys.path.insert(0, tree)
    import markdown
    got = os.path.dirname(os.path.abspath(markdown.__file__))
    assert got.startswith(os.path.abspath(tree)), (got, tree)
    return markdown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True,
                    help="pristine checkout of Python-Markdown")
    ap.add_argument("--impl", choices=["baseline", "optimized"], required=True)
    ap.add_argument("--patched", action="store_true",
                    help="copy the upstream tree and apply patch.diff")
    ap.add_argument("--out", default=None)
    ap.add_argument("--upstream-tests", default=None,
                    help="exact command + observed result (recorded verbatim)")
    args = ap.parse_args()

    upstream = os.path.abspath(args.upstream)
    tree = prepare_optimized(upstream) if args.patched else upstream
    markdown = load_markdown(tree)
    out_path = args.out or os.path.join(
        REPO_ROOT, "benchmark", f"{args.impl}.json")
    os.makedirs(RAW_DIR, exist_ok=True)

    report = {
        "impl": args.impl,
        "tree": tree,
        "upstream": upstream,
        "markdown_version": getattr(markdown, "__version__", "unknown"),
        "markdown_file": markdown.__file__,
        "seed": SEED,
        "warmup": WARMUP,
        "samples_per_scale": SAMPLES,
        "scales": {},
        "raw_files": [],
        "command": " ".join([sys.executable] + sys.argv),
        "env": {
            "python": sys.version.split()[0],
            "cpu": cpu_model(),
            "mem_total_kb": mem_total_kb(),
        },
        "upstream_tests": args.upstream_tests,
    }

    for scale, n_defs in SCALES:
        doc = build_doc(n_defs)
        doc_hash = hashlib.sha256(doc.encode()).hexdigest()
        for _ in range(WARMUP):
            markdown.markdown(doc, extensions=[EXT])
        seconds = []
        html_hashes = []
        for i in range(SAMPLES):
            t0 = time.perf_counter()
            html = markdown.markdown(doc, extensions=[EXT])
            dt = time.perf_counter() - t0
            seconds.append(dt)
            h = hashlib.sha256(html.encode()).hexdigest()
            html_hashes.append(h)
            raw = {
                "impl": args.impl, "scale": scale, "n_defs": n_defs,
                "sample": i, "warmup": WARMUP,
                "elapsed_s": dt, "doc_sha256": doc_hash,
                "html_sha256": h, "doc_bytes": len(doc.encode()),
                "seed": SEED, "python": sys.version.split()[0],
                "timer": "time.perf_counter",
            }
            name = f"{args.impl}-{scale}-{i}.json"
            with open(os.path.join(RAW_DIR, name), "w") as fh:
                json.dump(raw, fh, indent=1, sort_keys=True)
            report["raw_files"].append(f"benchmark/raw/{name}")
        p25, med, p75 = percentiles(seconds)
        mean = statistics.fmean(seconds)
        sd = statistics.stdev(seconds) if len(seconds) > 1 else 0.0
        report["scales"][scale] = {
            "n_defs": n_defs, "samples": SAMPLES,
            "seconds": seconds, "median_s": med, "p25_s": p25, "p75_s": p75,
            "mean_s": mean, "stdev_s": sd,
            "rsd": (sd / mean) if mean else 0.0,
            "html_sha256_unique": sorted(set(html_hashes)),
        }
    report["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print(f"[{args.impl}] -> {out_path}")
    for scale, data in report["scales"].items():
        print(f"  {scale:7s} n={data['n_defs']:5d} "
              f"median={data['median_s']:.6f}s "
              f"p25={data['p25_s']:.6f} p75={data['p75_s']:.6f} "
              f"rsd={data['rsd']*100:.1f}%")
    print(f"  peak_rss={report['peak_rss_kb']} kB")


if __name__ == "__main__":
    main()
