"""Deterministic test-case generator shared by tests/test_diff.py.

Every case is a Markdown document exercising the `abbr` extension's
block processor: consecutive definitions, definitions interleaved with
blocks, invalid definitions, regex metacharacters, non-ASCII text,
boundary inputs and very long runs.

`iter_cases()` must be deterministic (fixed seed) so that the baseline
and optimized modules are fed byte-identical inputs.
"""
import random

SEED = 20261101
N_RANDOM_CASES = 2400

NAMES = [
    "HTML", "CSS", "JS", "TS", "API", "URL", "URI", "HTTP", "TCP", "UDP",
    "JSON", "YAML", "TOML", "SQL", "XSS", "CSRF", "DOM", "SSR", "CDN", "DNS",
    "a.b", "a*b", "a+b", "a?b", "a|b", "a(b)", "a[b]", "a^b", "a$b", "a\\b",
    "café", "naïve", "北京", "東京", "Ω", "λ-calculus", "x=y", "!bang",
]

TITLES = [
    "HyperText Markup Language", "Cascading Style Sheets", "JavaScript",
    "TypeScript", "Application Programming Interface", "", "   ",
    "''", '""', "a title with 'quotes'", "title with | pipe",
    "title with \\ backslash", "标题", "emoji 🎉 title", "x" * 300,
    "trailing space ", " leading space",
]

BODIES = [
    "",
    "\nBody text using {n0} and {n1}.\n",
    "\n{n0}\n\n{n1}\n",
    "\n# Heading with {n0}\n\nParagraph {n1} {n0}.\n",
    "\n- item {n0}\n- item {n1}\n",
    "\n> quote {n0}\n> more {n1}\n",
    "\n    indented code {n0} {n1}\n",
    "\n`inline {n0}` and **{n1}**\n",
    "\n<div>{n0}</div>\n",
    "\nline one {n0}  \nline two {n1}\n",
]

INVALID_LINES = [
    "*[]: empty abbr name",
    "*[OK]: ",
    "*[  ]: blank abbr",
    "*[OK]:''",
    "*[OK]:\"\"",
]


def _def_line(rnd, idx):
    style = rnd.randrange(6)
    name = rnd.choice(NAMES)
    title = rnd.choice(TITLES)
    if style == 0:
        return f"*[{name}]: {title}"
    if style == 1:
        return f"*[{name}]:{title}"
    if style == 2:
        return f"*[{name}]:\n  {title}" if title else f"*[{name}]:"
    if style == 3:
        return f"*[{name}]: {title}\n"
    if style == 4:
        return f"  *[{name}]: {title}"
    return f"*[{name}{idx}]: {title}"


def _boundary_cases():
    cases = []
    cases.append(("empty", ""))
    cases.append(("just_newline", "\n"))
    cases.append(("only_space", "   \n\n"))
    cases.append(("single_def", "*[HTML]: HyperText Markup Language\n"))
    cases.append(("single_def_no_nl", "*[HTML]: HyperText Markup Language"))
    cases.append(("def_then_body", "*[HTML]: HyperText\n\nHTML here.\n"))
    cases.append(("body_then_def", "HTML here.\n\n*[HTML]: HyperText\n"))
    cases.append(("invalid_first", "*[]: nope\n*[OK]: fine\n\nOK\n"))
    cases.append(("invalid_middle",
                  "*[AA]: one\n*[]: nope\n*[BB]: two\n\nAA BB\n"))
    cases.append(("delete_def", "*[AA]: one\n*[AA]: ''\n\nAA\n"))
    cases.append(("reset_quotes", "*[AA]: one\n*[AA]: \"\"\n\nAA\n"))
    cases.append(("dup_def", "*[AA]: one\n*[AA]: two\n\nAA\n"))
    cases.append(("regex_meta", "*[a.b]: dotted\n*[a*b]: star\n\na.b a*b\n"))
    cases.append(("regex_brackets", "*[a(b)]: paren\n*[a[b]]: bracket\n\na(b) a[b]\n"))
    cases.append(("non_ascii", "*[北京]: 首都\n*[café]: coffee\n\n北京 café\n"))
    cases.append(("emoji", "*[🎉]: party\n\n🎉\n"))
    cases.append(("crlf", "*[AA]: one\r\n*[BB]: two\r\n\r\nAA BB\r\n"))
    cases.append(("no_trailing_nl_defs", "*[AA]: one\n*[BB]: two"))
    cases.append(("defs_then_blank_then_defs",
                  "*[AA]: one\n*[BB]: two\n\n*[CC]: three\n\nAA BB CC\n"))
    cases.append(("long_title", "*[AA]: " + "t" * 5000 + "\n\nAA\n"))
    cases.append(("many_defs_50",
                  "".join(f"*[AB{i}]: title {i}\n" for i in range(50)) + "\nAB0 AB49\n"))
    cases.append(("many_defs_300",
                  "".join(f"*[AB{i}]: title {i}\n" for i in range(300)) + "\nAB0 AB299\n"))
    cases.append(("defs_with_blank_between",
                  "*[AA]: one\n\n*[BB]: two\n\nAA BB\n"))
    cases.append(("indented_def", "  *[AA]: one\n\nAA\n"))
    cases.append(("def_in_blockquote", "> *[AA]: one\n\nAA\n"))
    cases.append(("heading_between",
                  "*[AA]: one\n\n# H\n\n*[BB]: two\n\nAA BB\n"))
    cases.append(("nested_list_defs",
                  "* top\n  *[AA]: one\n\nAA\n"))
    cases.append(("tab_indent", "\t*[AA]: one\n\nAA\n"))
    cases.append(("null_like", "*[AA]: \x00\n\nAA\n"))
    for i, bad in enumerate(INVALID_LINES):
        cases.append((f"invalid_style_{i}", bad + "\n*[ZZ]: good\n\nZZ\n"))
    return cases


def iter_cases():
    """Yield (case_id, markdown_text) deterministically."""
    for name, text in _boundary_cases():
        yield f"boundary::{name}", text

    rnd = random.Random(SEED)
    for k in range(N_RANDOM_CASES):
        parts = []
        n_defs = rnd.choice([1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 120, 400])
        for i in range(n_defs):
            if rnd.random() < 0.06:
                parts.append(rnd.choice(INVALID_LINES))
            else:
                parts.append(_def_line(rnd, i))
            if rnd.random() < 0.15:
                parts.append("")
            if rnd.random() < 0.08:
                parts.append(rnd.choice(BODIES).format(n0="AB0", n1="AB1"))
        body = rnd.choice(BODIES).format(n0=rnd.choice(NAMES), n1=rnd.choice(NAMES))
        text = "".join(
            p if p.endswith("\n") or p == "" else p + "\n" for p in parts
        ) + body
        yield f"random::{k}", text
