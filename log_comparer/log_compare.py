#!/usr/bin/env python3
import argparse
import curses
import difflib
import re
import json
import ast
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

COLOR_NAMES = {
    'black': curses.COLOR_BLACK,
    'red': curses.COLOR_RED,
    'green': curses.COLOR_GREEN,
    'yellow': curses.COLOR_YELLOW,
    'blue': curses.COLOR_BLUE,
    'magenta': curses.COLOR_MAGENTA,
    'cyan': curses.COLOR_CYAN,
    'white': curses.COLOR_WHITE,
}


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


def wrap_segments(text, width, offset=0, wrap_mode=True):
    if width <= 0:
        return [""]
    if offset < 0:
        offset = 0
    text = (text or "")[offset:]
    if not wrap_mode:
        return [fit(text[:width], width)]
    segments = []
    while text:
        segments.append(fit(text[:width], width))
        text = text[width:]
    if not segments:
        segments.append(" " * width)
    return segments


class LogComparer:
    def __init__(self, a_lines, b_lines, left_name, right_name, tag_patterns=None, debug_mode=False):
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
        self.tag_patterns = tag_patterns or []
        self.debug_mode = debug_mode
        self.debug_path = Path(__file__).resolve().parent / 'tmp_log_comparer.log'
        if self.debug_mode:
            try:
                self.debug_path.write_text('')
            except Exception:
                pass
        self.show_tag = False
        self.wrap_mode = True
        self.left_width_fraction = 0.5
        self.offset = 0
        self.tag_color_fg = None
        self.tag_color_bg = None
        self.tag_color_pair = None
        self.top_row = 0

        self.rows = []
        self.build_rows()

    def log_debug(self, msg: str):
        if not getattr(self, 'debug_mode', False):
            return
        try:
            from datetime import datetime, timezone
            entry = f"{datetime.now(timezone.utc).isoformat()} {msg}\n"
            with open(self.debug_path, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            pass
    

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
                # rows: (marker, left_text, right_text, left_line_no, right_line_no, tag_flag)
                tag_flag = False
                for p in self.tag_patterns:
                    try:
                        if (ltxt and re.search(p, ltxt, re.IGNORECASE)) or (rtxt and re.search(p, rtxt, re.IGNORECASE)):
                            tag_flag = True
                            break
                    except re.error:
                        # invalid regex, fallback to literal
                        if (ltxt and p.lower() in ltxt.lower()) or (rtxt and p.lower() in rtxt.lower()):
                            tag_flag = True
                            break
                self.rows.append((marker, ltxt, rtxt, lnum, rnum, tag_flag))

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
        # optionally include tagged lines
        if self.show_tag:
            tag_idxs = [i for i, row in enumerate(self.rows) if row[5]]
            for i in tag_idxs:
                visible.add(i)
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

    def max_line_offset(self):
        max_len = 0
        for _, left, right, _, _, _ in self.rows:
            max_len = max(max_len, len(left or ""), len(right or ""))
        return max(0, max_len - 1)


def run_curses(stdscr, comparer: LogComparer):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    tag_color_pair = 3
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        fg = COLOR_NAMES.get(str(comparer.tag_color_fg).lower(), curses.COLOR_BLACK)
        bg = COLOR_NAMES.get(str(comparer.tag_color_bg).lower(), curses.COLOR_YELLOW)
        curses.init_pair(tag_color_pair, fg, bg)
        comparer.tag_color_pair = tag_color_pair
    else:
        comparer.tag_color_pair = None

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        gutter = 3
        # reserve space for optional line numbers on both sides
        number_width = 0
        if comparer.show_line_numbers:
            number_width = max(4, len(str(max(1, max(len(comparer.a_lines), len(comparer.b_lines))))))
        content_width = width - gutter - number_width * 2
        if content_width < 20:
            content_width = max(20, width - gutter)
        left_width = max(10, int(content_width * comparer.left_width_fraction))
        right_width = max(10, content_width - left_width)
        if right_width < 10:
            right_width = 10
            left_width = max(10, content_width - right_width)

        # header
        header = f" {comparer.left_name} "
        header2 = f" {comparer.right_name} "
        stdscr.addnstr(0, 0, header, left_width, curses.color_pair(2))
        stdscr.addnstr(0, left_width + gutter, header2, right_width, curses.color_pair(2))

        # mode line
        mode = "ALL" if comparer.view_all_mode else "DIFF"
        ln = "ON" if comparer.show_line_numbers else "OFF"
        hd = "ON" if comparer.highlight_diffs else "OFF"
        wp = "ON" if comparer.wrap_mode else "OFF"
        width_pct = int(comparer.left_width_fraction * 8) / 8.0
        mode_line = (
            f"Mode:{mode} ctx={comparer.diff_context}  lnum={ln}  hdiff={hd}  wrap={wp}  "
            f"left={width_pct:.3g} off={comparer.offset}  / a:all d:diff 0-9:set ctx  "
            f"[:smaller ]:larger w:wrap ←/→:horiz Tab/Shift-Tab:offset  s:search  PgUp/PgDn:page  ↑/↓:line  l:line#  h:highlight  q:quit"
        )
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

        y = 3
        for idx_on_screen in range(page_size):
            vi = page_top + idx_on_screen
            if vi >= total_rows:
                break
            row_idx = visible[vi]
            marker, left, right, lnum, rnum, tag = comparer.rows[row_idx]

            left_segments = wrap_segments(left, left_width, comparer.offset, comparer.wrap_mode)
            right_segments = wrap_segments(right, right_width, comparer.offset, comparer.wrap_mode)
            block_lines = max(len(left_segments), len(right_segments), 1)

            for sub_idx in range(block_lines):
                if y >= height - 1:
                    break
                ltxt = left_segments[sub_idx] if sub_idx < len(left_segments) else " " * left_width
                rtxt = right_segments[sub_idx] if sub_idx < len(right_segments) else " " * right_width
                sub_marker = marker if sub_idx == 0 else " "
                sub_lnum = lnum if sub_idx == 0 else None
                sub_rnum = rnum if sub_idx == 0 else None

                # positions
                left_col_x = 0
                left_text_x = left_col_x
                if comparer.show_line_numbers:
                    left_text_x = left_col_x + number_width + 1

                marker_x = left_text_x + left_width + 1
                right_text_x = left_text_x + left_width + 3

                # draw left number and text
                try:
                    if comparer.show_line_numbers:
                        num = f"{sub_lnum or '':>{number_width}} "
                        stdscr.addnstr(y, left_col_x, num, number_width + 1)
                    attr = 0
                    if comparer.highlight_diffs and marker != " ":
                        attr = curses.A_REVERSE
                    stdscr.addnstr(y, left_text_x, ltxt, left_width, attr)
                except curses.error:
                    pass

                # marker
                try:
                    stdscr.addch(y, marker_x, sub_marker)
                except curses.error:
                    pass

                # draw right number and text
                try:
                    if comparer.show_line_numbers:
                        numr = f"{sub_rnum or '':>{number_width}} "
                        stdscr.addnstr(y, right_text_x - (number_width + 1), numr, number_width + 1)
                    attr_r = 0
                    if comparer.highlight_diffs and marker != " ":
                        attr_r = curses.A_REVERSE
                    stdscr.addnstr(y, right_text_x, rtxt, right_width, attr_r)
                except curses.error:
                    pass

                # tag highlight
                if tag and comparer.show_tag and comparer.tag_color_pair:
                    try:
                        stdscr.addnstr(y, left_text_x, ltxt, left_width, curses.color_pair(comparer.tag_color_pair))
                        stdscr.addnstr(y, right_text_x, rtxt, right_width, curses.color_pair(comparer.tag_color_pair))
                    except curses.error:
                        pass

                # highlight search matches
                if comparer.highlight_pattern:
                    for m in re.finditer(comparer.highlight_pattern, ltxt or "", re.IGNORECASE):
                        try:
                            start = m.start()
                            if start < left_width:
                                stdscr.addnstr(y, left_text_x + start, ltxt[start:start + (m.end() - m.start())], m.end() - m.start(), curses.color_pair(1))
                        except curses.error:
                            pass
                    for m in re.finditer(comparer.highlight_pattern, rtxt or "", re.IGNORECASE):
                        try:
                            start = m.start()
                            if start < right_width:
                                stdscr.addnstr(y, right_text_x + start, rtxt[start:start + (m.end() - m.start())], m.end() - m.start(), curses.color_pair(1))
                        except curses.error:
                            pass

                y += 1

        # footer
        footer = f"Rows {page_top + 1}-{min(page_top + page_size, total_rows)} / {total_rows}"
        stdscr.addnstr(height - 1, 0, footer, width - 1)

        stdscr.refresh()

        def key_name(k):
            if k in (None, -1):
                return ''
            if 0 <= k <= 255:
                try:
                    ch = chr(k)
                    if ch.isprintable():
                        return ch
                except Exception:
                    pass
            if k == curses.KEY_UP:
                return 'UP'
            if k == curses.KEY_DOWN:
                return 'DOWN'
            if k == curses.KEY_NPAGE:
                return 'PGDN'
            if k == curses.KEY_PPAGE:
                return 'PGUP'
            if k == curses.KEY_RESIZE:
                return 'RESIZE'
            return str(k)

        def flash(msg, ms=200):
            try:
                stdscr.addnstr(0, 0, msg.ljust(width - 1), width - 1, curses.A_BOLD)
                stdscr.refresh()
                curses.napms(ms)
            except curses.error:
                pass

        key = stdscr.getch()
        try:
            comparer.log_debug(f"key_pressed {key_name(key)} ({key})")
        except Exception:
            pass

        # hotkey set to show flash message
        hotkeys = {
            ord('q'), ord('Q'), ord('a'), ord('A'), ord('d'), ord('D'),
            ord('s'), ord('S'), ord('l'), ord('L'), ord('h'), ord('H'), ord('t'), ord('T'),
            ord('w'), ord('W'), ord('['), ord(']'), ord('\t'),
            curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_NPAGE, curses.KEY_PPAGE, curses.KEY_BTAB
        }
        if (0 <= key <= 255 and chr(key).isdigit()) or key in hotkeys:
            name = key_name(key)
            if name:
                flash(f"processing {name}")
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
        if key == curses.KEY_RIGHT:
            comparer.offset += 1
            if comparer.offset > comparer.max_line_offset():
                comparer.offset = comparer.max_line_offset()
            continue
        if key == curses.KEY_LEFT:
            comparer.offset -= 1
            if comparer.offset < 0:
                comparer.offset = 0
            continue
        if key == ord('\t'):
            if not comparer.wrap_mode:
                comparer.offset += 16
                if comparer.offset > comparer.max_line_offset():
                    comparer.offset = comparer.max_line_offset()
            continue
        if key == curses.KEY_BTAB:
            if not comparer.wrap_mode:
                comparer.offset -= 16
                if comparer.offset < 0:
                    comparer.offset = 0
            continue
        if key in (ord('l'), ord('L')):
            comparer.show_line_numbers = not comparer.show_line_numbers
            comparer.top_row = 0
            continue
        if key in (ord('h'), ord('H')):
            comparer.highlight_diffs = not comparer.highlight_diffs
            comparer.log_debug(f"highlight_diffs set to {comparer.highlight_diffs}")
            continue
        if key in (ord('w'), ord('W')):
            comparer.wrap_mode = not comparer.wrap_mode
            comparer.log_debug(f"wrap_mode set to {comparer.wrap_mode}")
            comparer.top_row = 0
            continue
        if key in (ord('t'), ord('T')):
            # toggle tag-line visibility (only meaningful in diff mode)
            comparer.show_tag = not comparer.show_tag
            comparer.log_debug(f"show_tag toggled to {comparer.show_tag}")
            comparer.top_row = 0
            continue
        if key == curses.KEY_NPAGE or key == ord(' '):
            comparer.top_row += page_size
            if comparer.top_row > max(0, total_rows - page_size):
                comparer.top_row = max(0, total_rows - page_size)
            continue
        if key == ord('['):
            fractions = [1/8, 1/4, 1/2, 3/4, 7/8]
            current = comparer.left_width_fraction
            next_index = max(0, min(len(fractions) - 1, fractions.index(current) - 1 if current in fractions else 2))
            comparer.left_width_fraction = fractions[next_index]
            comparer.top_row = 0
            continue
        if key == ord(']'):
            fractions = [1/8, 1/4, 1/2, 3/4, 7/8]
            current = comparer.left_width_fraction
            next_index = min(len(fractions) - 1, fractions.index(current) + 1 if current in fractions else 2)
            comparer.left_width_fraction = fractions[next_index]
            comparer.top_row = 0
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

    # load optional setup.json in the same folder as this script
    tag_patterns = []
    debug_mode = False
    tag_fg_color = None
    tag_bg_color = None
    cfg = {}
    setup_path = Path(__file__).resolve().parent / 'setup.json'
    if setup_path.exists():
        raw = setup_path.read_text(encoding='utf-8')
        try:
            cfg = json.loads(raw)
        except Exception:
            try:
                # try to parse Python-style dict (allows r'...' patterns)
                cfg = ast.literal_eval(raw)
            except Exception as e:
                print('Warning: failed to read setup.json:', e)
                cfg = {}

    # default config
    default_cfg = cfg.get('default_config', {}) or {}
    debug_mode = bool(default_cfg.get('debug_mode', False))

    rp = cfg.get('replace_patterns') or cfg.get('REPLACE_PATTERNS')
    if isinstance(rp, list):
        for item in rp:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                REPLACEMENTS.append((str(item[0]), str(item[1])))
            elif isinstance(item, dict) and 'pattern' in item and 'replace' in item:
                REPLACEMENTS.append((str(item['pattern']), str(item.get('replace', ''))))
    elif isinstance(rp, dict):
        for name, pattern in rp.items():
            REPLACEMENTS.append((str(pattern), f"<{name}>") )

    tp = cfg.get('tag_patterns') or cfg.get('TAG_PATTERNS')
    if isinstance(tp, list):
        tag_patterns = [str(x) for x in tp if x]
    elif isinstance(tp, dict):
        tag_patterns = [str(v) for v in tp.values() if v]

    color_cfg = cfg.get('colors', {}) or {}
    tag_fg_color = color_cfg.get('tag_foreground')
    tag_bg_color = color_cfg.get('tag_background')

    a_lines = load_lines(args.left, ignore_case=args.ignore_case)
    b_lines = load_lines(args.right, ignore_case=args.ignore_case)

    comparer = LogComparer(a_lines, b_lines, args.left, args.right, tag_patterns=tag_patterns, debug_mode=debug_mode)
    comparer.tag_color_fg = tag_fg_color
    comparer.tag_color_bg = tag_bg_color
    comparer.view_all_mode = bool(default_cfg.get('view_all_mode', comparer.view_all_mode))
    comparer.view_diff_mode = bool(default_cfg.get('view_diff_mode', comparer.view_diff_mode))
    comparer.diff_context = int(default_cfg.get('diff_context', comparer.diff_context))
    comparer.show_line_numbers = bool(default_cfg.get('show_line_numbers', comparer.show_line_numbers))
    comparer.highlight_diffs = bool(default_cfg.get('highlight_diffs', comparer.highlight_diffs))
    return curses.wrapper(run_curses, comparer)


if __name__ == '__main__':
    main()

