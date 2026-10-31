# markdown-opt-lab — removing the last O(n²) block-processor loop in Python-Markdown

[Python-Markdown](https://github.com/Python-Markdown/markdown) is the reference Markdown
implementation for Python. This lab changes **one function**:
`markdown/extensions/abbr.py::AbbrBlockprocessor.run` consumed one abbreviation
definition per call and pushed the rest of the block back onto the block queue, so a run of
*n* consecutive `*[ABBR]: title` definitions was re-scanned by every block processor O(*n*)
times — quadratic. The patch consumes the run in **one pass** (`RE.finditer` + a single
queue splice). Result: **88.1× median speedup** (18.7× / 88.1× / 379.3× at three scales),
**2434 differential cases byte-identical**, all **1187 upstream tests green**, peak RSS
1.007× of baseline.

Upstream: https://github.com/Python-Markdown/markdown

## What changed

`patch.diff` (65 changed lines: 48 insertions, 17 deletions) replaces the per-definition
search-and-requeue in `AbbrBlockprocessor.run` with a single `finditer` pass over the block.
Prefixes, suffixes and invalid-definition fallback are emitted in the same order the old
loop produced them, so block splitting and the `abbrs` registry semantics are unchanged.
No public API, no return-value semantics, no upstream test file was touched.

```
-$ m = self.RE.search(block)          # once per definition -> O(n) rescans
+matches = list(self.RE.finditer(block))   # one pass -> O(n)
```

## Results (median of 5 timed samples after 3 warmups)

| scale | n definitions | baseline median | optimized median | speedup |
|------|---------------|-----------------|------------------|---------|
| small | 150 | 0.019660 s | 0.001049 s | **18.7×** |
| medium | 600 | 0.307660 s | 0.003494 s | **88.1×** |
| large | 2400 | 5.563300 s | 0.014668 s | **379.3×** |

Rendered HTML is byte-identical in all three scales (`html_sha256_unique` in
`benchmark/*.json`). Baseline run-to-run RSD: small 0.5%, medium 1.2%, large 6.9% (the large
scale spends seconds per sample, so GC / page-fault jitter is visible; p25/p75 are
4.948/5.575 s). Optimized RSD: 7.0% / 0.7% / 0.6%. The gain is algorithmic, not a constant
factor: per-sample medians follow the O(n²)→O(n) change over a 16× span of n.

## Evidence and gates

- **G2 · differential, byte-identical**: 2434 cases (random + boundary: empty, single
  definition, invalid/empty definitions, `''`/`""` resets, duplicate names, regex
  metacharacters, CRLF, non-ASCII/CJK/emoji, 5000-char titles, 50/300/400-definition runs).
  SHA-256 of the exact rendered HTML compared, 0 differences; re-run of the optimized tree is
  deterministic.
  `MD_UPSTREAM=/tmp/md-upstream python3 -m pytest tests/test_diff.py -q -s`
- **G1 · upstream tests green**: 1187 tests, `OK (skipped=111)`, 0 failed, on the patched tree.
  ```bash
  git clone --depth=1 git@github-linluozi:Python-Markdown/markdown.git /tmp/md-g1
  python3 -m venv /tmp/venv-g1 && /tmp/venv-g1/bin/pip install -q -e /tmp/md-g1
  git -C /tmp/md-g1 apply -p1 patch.diff
  cd /tmp/md-g1 && /tmp/venv-g1/bin/python -m unittest discover tests
  ```
- **G3 · median speedup** 88.1× ≥ 1.15× (see table; produced by the bench commands below).
- **G4 · no large-scale regression**: large scale 379.3×, far above 0.95×.
- **G5 · memory**: peak RSS 30400 kB baseline → 30600 kB optimized = **1.007×** ≤ 1.10×
  (`peak_rss_kb` in `benchmark/baseline.json` / `optimized.json`, measured with
  `resource.getrusage(RUSAGE_SELF).ru_maxrss` inside the same process that times the runs).

## Reproduce (copy-paste)

```bash
git clone --depth=1 git@github-linluozi:Python-Markdown/markdown.git /tmp/md-upstream
MD_UPSTREAM=/tmp/md-upstream python3 -m pytest tests/test_diff.py -q -s
python3 benchmark/bench.py --upstream /tmp/md-upstream --impl baseline \
  && python3 benchmark/bench.py --upstream /tmp/md-upstream --impl optimized --patched
```
(`benchmark/bench.py` inserts the chosen checkout at `sys.path[0]` and asserts the imported
`markdown` really comes from it; `benchmark/raw/` keeps all 30 raw samples.)

## Environment

CPU AMD EPYC 7K62 (4 vCPU), RAM 3812564 kB, Python 3.12.3, Markdown 3.11.2 (upstream commit
`0bfd8c3`), seed 20261101, timer `time.perf_counter()`.

## 本轮创新

**B 档。** 上游 HEAD 提交 `0bfd8c3` 刚修掉 *reference definition* 的二次方解析，但同一类
「每轮只消费一个定义、把剩余块回填队列」的循环在 `abbr` 扩展里仍然存在；本轮首次指认该残留
实例、给出 18.7×/88.1×/379.3× 的三规模量化与 2434 组逐字节等价证明，并用单遍
`finditer` + 一次队列拼接把它线性化（不是单行换皮：改动涉及前缀/后缀/非法定义三条回退路径
的顺序保持）。与台账里已发布的 jsonpath/dpath/jsondiff 等条目不同，本条是 O(n²) 消除 +
上游同批次修复的对照测量。
