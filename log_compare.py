#!/usr/bin/env python3
import argparse
import difflib
import re
import shutil
from pathlib import Path

REPLACEMENTS = [
    (r'\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b', '<TIME>'),
    (r'\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b', '<TIME>'),
    (r'\bpid=\d+\b', 'pid=<PID>'),
    (r'\btid=\d+\b', 'tid=<TID>'),
    (r'\bthread=\d+\b', 'thread=<THREAD>'),
    (r'0x[0-9a-fA-F]+\b', '0x<HEX>'),
]

DROP_PATTERNS = [
    r'heartbeat',
    r'health check',
    r'polling',
]

def normalize_line(line, ignore_case=False):
    s = line.rstrip("\n")
    for pat, repl in REPLACEMENTS:
        s = re.sub(pat, repl, s)
    if ignore_case:
        s = s.lower()
    return s

def keep_line(line):
    return not any(re.search(p, line, re.IGNORECASE) for p in DROP_PATTERNS)

def load_lines(path, ignore_case=False):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        line = normalize_line(line, ignore_case=ignore_case)
        if keep_line(line):
            lines.append(line)
    return lines

def fit(text, width):
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return "…"
    return text[:width - 1] + "…"

def print_side_by_side(a_lines, b_lines, total_width=None):
    total_width = total_width or shutil.get_terminal_size((160, 40)).columns
    gutter = 3
    col_width = max(20, (total_width - gutter) // 2)

    sm = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        left = a_lines[i1:i2]
        right = b_lines[j1:j2]
        rows = max(len(left), len(right))

        if tag == "equal":
            marker = " "
        elif tag == "replace":
            marker = "|"
        elif tag == "delete":
            marker = "<"
        elif tag == "insert":
            marker = ">"
        else:
            marker = "?"

        for idx in range(rows):
            ltxt = left[idx] if idx < len(left) else ""
            rtxt = right[idx] if idx < len(right) else ""
            print(f"{fit(ltxt, col_width)} {marker} {fit(rtxt, col_width)}")

def main():
    parser = argparse.ArgumentParser(description="Terminal side-by-side log diff")
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--width", type=int, help="override terminal width")
    parser.add_argument("--ignore-case", action="store_true")
    args = parser.parse_args()

    a_lines = load_lines(args.left, ignore_case=args.ignore_case)
    b_lines = load_lines(args.right, ignore_case=args.ignore_case)

    print_side_by_side(a_lines, b_lines, total_width=args.width)

if __name__ == "__main__":
    main()
