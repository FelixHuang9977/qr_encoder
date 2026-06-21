#!/usr/bin/env python3
import curses

def select_menu(stdscr, items, title="Select an item"):
    curses.curs_set(0)
    stdscr.keypad(True)

    current = 0
    top = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        visible_rows = max(1, height - 2)  # 1 line for title, rest for items

        if current < top:
            top = current
        elif current >= top + visible_rows:
            top = current - visible_rows + 1

        stdscr.addnstr(0, 0, title, width - 1)

        end = min(len(items), top + visible_rows)
        for row, idx in enumerate(range(top, end), start=1):
            prefix = "> " if idx == current else "  "
            text = prefix + str(items[idx])

            if idx == current:
                stdscr.addnstr(row, 0, text, width - 1, curses.A_REVERSE)
            else:
                stdscr.addnstr(row, 0, text, width - 1)

        key = stdscr.getch()

        if key == 27:  # ESC
            return None
        elif key == curses.KEY_UP:
            if current > 0:
                current -= 1
        elif key == curses.KEY_DOWN:
            if current < len(items) - 1:
                current += 1
        elif key == curses.KEY_PPAGE:  # Page Up
            current = max(0, current - visible_rows)
        elif key == curses.KEY_NPAGE:  # Page Down
            current = min(len(items) - 1, current + visible_rows)
        elif key == curses.KEY_HOME:
            current = 0
        elif key == curses.KEY_END:
            current = len(items) - 1
        elif key in (10, 13, curses.KEY_ENTER):
            return current

def main():
    items = [f"Item {i}" for i in range(1, 101)]
    selected = curses.wrapper(select_menu, items, "Use arrows / PgUp / PgDn / Home / End / Enter, Esc quits")

    if selected is None:
        print("Quit without selection")
    else:
        print(f"Selected index={selected}, value={items[selected]}")

if __name__ == "__main__":
    main()
