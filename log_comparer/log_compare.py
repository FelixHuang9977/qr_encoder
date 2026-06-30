#!/usr/bin/env python3
import argparse
import curses
import difflib
import re
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


class LogComparer:
    def __init__(self, a_lines, b_lines, left_name, right_name):
        self.a_lines = a_lines
        self.b_lines = b_lines
        self.left_name = left_name
        self.right_name = right_name

        self.view_all_mode = False
        self.view_diff_mode = True
        self.diff_context = 1
        self.show_line_numbers = False
        self.highlight_diffs = False
        self.highlight_pattern = None

        self.top_row = 0

        self.rows = []
        self.build_rows()

    def build_rows(self):
        self.rows = []
        sm = difflib.SequenceMatcher(None, self.a_lines, self.b_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            left = self.a_lines[i1:i2]
            right = self.b_lines[j1:j2]
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
                lnum = (i1 + idx + 1) if idx < len(left) else None
                rnum = (j1 + idx + 1) if idx < len(right) else None
                # rows: (marker, left_text, right_text, left_line_no, right_line_no)
                self.rows.append((marker, ltxt, rtxt, lnum, rnum))

    def visible_indices(self):
        if self.view_all_mode:
            return list(range(len(self.rows)))

        # view_diff_mode: include diff rows and context
        diff_idxs = [i for i, row in enumerate(self.rows) if row[0] != " "]
        visible = set()
        for i in diff_idxs:
            for k in range(i - self.diff_context, i + self.diff_context + 1):
                if 0 <= k < len(self.rows):
                    visible.add(k)
        return sorted(visible)

    def search_matches(self, text):
        if not self.highlight_pattern:
            return []
        try:
            return [m for m in re.finditer(self.highlight_pattern, text, re.IGNORECASE)]
        except re.error:
            # treat pattern as literal substring
            idx = text.lower().find(self.highlight_pattern.lower())
            if idx == -1:
                return []
            return [re.match(re.escape(text[idx:idx + len(self.highlight_pattern)]), text[idx:idx + len(self.highlight_pattern)])]


def run_curses(stdscr, comparer: LogComparer):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(2, curses.COLOR_CYAN, -1)

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        gutter = 3
        # reserve space for optional line numbers on both sides
        number_width = 0
        if comparer.show_line_numbers:
            number_width = max(4, len(str(max(1, max(len(comparer.a_lines), len(comparer.b_lines))))))
        col_width = max(10, (width - gutter - number_width * 2) // 2)

        # header
        header = f" {comparer.left_name} "
        header2 = f" {comparer.right_name} "
        stdscr.addnstr(0, 0, header, col_width, curses.color_pair(2))
        stdscr.addnstr(0, col_width + gutter, header2, col_width, curses.color_pair(2))

        # mode line
        mode = "ALL" if comparer.view_all_mode else "DIFF"
        ln = "ON" if comparer.show_line_numbers else "OFF"
        hd = "ON" if comparer.highlight_diffs else "OFF"
        mode_line = f"Mode:{mode} ctx={comparer.diff_context}  lnum={ln}  hdiff={hd}  / a:all d:diff 0-9:set ctx  s:search  PgUp/PgDn:page  ↑/↓:line  l:line#  h:highlight  q:quit"
        stdscr.addnstr(1, 0, mode_line, width - 1)

        visible = comparer.visible_indices()
        total_rows = len(visible)

        page_top = comparer.top_row
        page_size = max(3, height - 4)

        # clamp
        if page_top < 0:
            page_top = 0
        if page_top > max(0, total_rows - 1):
            page_top = max(0, total_rows - 1)
        comparer.top_row = page_top

        for idx_on_screen in range(page_size):
            vi = page_top + idx_on_screen
            if vi >= total_rows:
                break
            row_idx = visible[vi]
            marker, left, right, lnum, rnum = comparer.rows[row_idx]

            y = idx_on_screen + 3
            ltxt = fit(left, col_width)
            rtxt = fit(right, col_width)

            # positions
            left_col_x = 0
            left_text_x = left_col_x
            if comparer.show_line_numbers:
                left_text_x = left_col_x + number_width + 1

            marker_x = left_text_x + col_width + 1
            right_text_x = left_text_x + col_width + 3

            # draw left number and text
            try:
                if comparer.show_line_numbers:
                    num = f"{lnum or '':>{number_width}} "
                    stdscr.addnstr(y, left_col_x, num, number_width + 1)
                attr = 0
                if comparer.highlight_diffs and marker != " ":
                    attr = curses.A_REVERSE
                stdscr.addnstr(y, left_text_x, ltxt, col_width, attr)
            except curses.error:
                pass

            # marker
            try:
                stdscr.addch(y, marker_x, marker)
            except curses.error:
                pass

            # draw right number and text
            try:
                if comparer.show_line_numbers:
                    numr = f"{rnum or '':>{number_width}} "
                    stdscr.addnstr(y, right_text_x - (number_width + 1), numr, number_width + 1)
                attr_r = 0
                if comparer.highlight_diffs and marker != " ":
                    attr_r = curses.A_REVERSE
                stdscr.addnstr(y, right_text_x, rtxt, col_width, attr_r)
            except curses.error:
                pass

            # highlight search matches
            if comparer.highlight_pattern:
                for m in re.finditer(comparer.highlight_pattern, left or "", re.IGNORECASE):
                    try:
                        start = m.start()
                        if start < col_width:
                            stdscr.addnstr(y, left_text_x + start, (left or "")[start:start + (m.end() - m.start())], m.end() - m.start(), curses.color_pair(1))
                    except curses.error:
                        pass
                for m in re.finditer(comparer.highlight_pattern, right or "", re.IGNORECASE):
                    try:
                        start = m.start()
                        if start < col_width:
                            stdscr.addnstr(y, right_text_x + start, (right or "")[start:start + (m.end() - m.start())], m.end() - m.start(), curses.color_pair(1))
                    except curses.error:
                        pass

        # footer
        footer = f"Rows {page_top + 1}-{min(page_top + page_size, total_rows)} / {total_rows}"
        stdscr.addnstr(height - 1, 0, footer, width - 1)

        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            comparer.build_rows()
            continue
        if key in (ord('q'), ord('Q')):
            break
        if key in (ord('a'), ord('A')):
            comparer.view_all_mode = True
            comparer.view_diff_mode = False
            comparer.top_row = 0
            continue
        if key in (ord('d'), ord('D')):
            comparer.view_all_mode = False
            comparer.view_diff_mode = True
            comparer.top_row = 0
            continue
        if ord('0') <= key <= ord('9'):
            comparer.diff_context = key - ord('0')
            comparer.top_row = 0
            continue
        if key == curses.KEY_DOWN:
            comparer.top_row += 1
            if comparer.top_row > max(0, total_rows - page_size):
                comparer.top_row = max(0, total_rows - page_size)
            continue
        if key == curses.KEY_UP:
            comparer.top_row -= 1
            if comparer.top_row < 0:
                comparer.top_row = 0
            continue
        if key in (ord('l'), ord('L')):
            comparer.show_line_numbers = not comparer.show_line_numbers
            comparer.top_row = 0
            continue
        if key in (ord('h'), ord('H')):
            comparer.highlight_diffs = not comparer.highlight_diffs
            continue
        if key == curses.KEY_NPAGE or key == ord(' '):
            comparer.top_row += page_size
            if comparer.top_row > max(0, total_rows - page_size):
                comparer.top_row = max(0, total_rows - page_size)
            continue
        if key == curses.KEY_PPAGE:
            comparer.top_row -= page_size
            if comparer.top_row < 0:
                comparer.top_row = 0
            continue
        if key in (ord('s'), ord('S')):
            # prompt for search
            curses.echo()
            curses.curs_set(1)
            stdscr.addstr(height - 2, 0, "Search: ")
            stdscr.clrtoeol()
            try:
                pat = stdscr.getstr(height - 2, 8, 60).decode('utf-8')
            except Exception:
                pat = ''
            curses.noecho()
            curses.curs_set(0)
            if pat:
                comparer.highlight_pattern = pat
            else:
                comparer.highlight_pattern = None
            continue


def main():
    parser = argparse.ArgumentParser(description="Terminal curses side-by-side log diff")
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--ignore-case", action="store_true")
    args = parser.parse_args()

    a_lines = load_lines(args.left, ignore_case=args.ignore_case)
    b_lines = load_lines(args.right, ignore_case=args.ignore_case)

    comparer = LogComparer(a_lines, b_lines, args.left, args.right)
    try:
        curses.wrapper(run_curses, comparer)
    except Exception as e:
        # fallback to non-curses print
        print("Error running curses UI:", e)
        for row in comparer.rows:
            marker, l, r, ln, rn = row
            print(f"{marker} {ln or ''} {l} | {rn or ''} {r}")


if __name__ == "__main__":
    main()
