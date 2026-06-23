#!/usr/bin/env python3
import curses
import argparse
import datetime
import sys

def get_default_days(today=None):
    """
    Returns 2 if today is Monday (weekday 0), otherwise 1.
    """
    if today is None:
        today = datetime.date.today()
    return 2 if today.weekday() == 0 else 1

def parse_arguments(args=None):
    """
    Parses command-line arguments: SA, SN, and --days.
    Validates that SN is numeric if provided.
    """
    default_days = get_default_days()
    parser = argparse.ArgumentParser(description="TUI Menu with SA/SN filtering")
    parser.add_argument('sa', nargs='?', default='', type=str, help='SA string filter')
    parser.add_argument('sn', nargs='?', default='', type=str, help='SN digit filter')
    parser.add_argument('--days', type=int, default=default_days, help='Number of days (default: 2 if Monday, else 1)')
    
    parsed = parser.parse_args(args)
    if parsed.sn and not parsed.sn.isdigit():
        parser.error("SN must be a string containing only digits.")
        
    return parsed

def matches_filter(item, sa_filter, sn_filter):
    """
    Checks if the given item matches the SA and SN filters.
    Supports dictionaries and objects with SA/SN attributes.
    """
    sa_filter = (sa_filter or "").strip().lower()
    sn_filter = (sn_filter or "").strip()

    if isinstance(item, dict):
        item_sa = str(item.get("SA") or item.get("sa") or "")
        item_sn = str(item.get("SN") or item.get("sn") or "")
    elif hasattr(item, "SA") or hasattr(item, "sa") or hasattr(item, "SN") or hasattr(item, "sn"):
        item_sa = str(getattr(item, "SA", getattr(item, "sa", "")))
        item_sn = str(getattr(item, "SN", getattr(item, "sn", "")))
    else:
        # Fallback for plain strings
        item_str = str(item)
        if sa_filter and sa_filter not in item_str.lower():
            return False
        if sn_filter and sn_filter not in item_str:
            return False
        return True

    if sa_filter and sa_filter not in item_sa.lower():
        return False
    if sn_filter and sn_filter not in item_sn:
        return False
    return True

def select_menu(stdscr, items, title="Select an item", initial_sa="", initial_sn=""):
    curses.curs_set(0)
    stdscr.keypad(True)

    sa_filter = initial_sa
    sn_filter = initial_sn
    focus_state = None  # None: item list, "SA": SA input field, "SN": SN input field

    current = 0
    top = 0

    dim_attr = getattr(curses, 'A_DIM', curses.A_NORMAL)

    while True:
        # Filter items dynamically and track their original indices
        filtered_with_indices = [
            (idx, item) for idx, item in enumerate(items)
            if matches_filter(item, sa_filter, sn_filter)
        ]
        
        # Clamp current index to the new filtered range
        if filtered_with_indices:
            current = max(0, min(current, len(filtered_with_indices) - 1))
        else:
            current = 0

        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # 3 lines of overhead: Title (0), Search bar (1), Separator (2)
        visible_rows = max(1, height - 4)  # Leave bottom line free to avoid scroll issues

        # Scroll calculation
        if current < top:
            top = current
        elif current >= top + visible_rows:
            top = current - visible_rows + 1

        # Draw Title (Row 0)
        try:
            stdscr.addnstr(0, 0, title, width - 1)
        except curses.error:
            pass

        # Draw Search Bar (Row 1)
        try:
            stdscr.move(1, 0)
            stdscr.addstr("Search - ")
            
            # SA Field
            if focus_state == "SA":
                stdscr.addstr("SA: ", curses.A_BOLD)
                stdscr.addstr("[ ", curses.A_NORMAL)
                stdscr.addstr(sa_filter or " ", curses.A_REVERSE)
                stdscr.addstr(" ]", curses.A_NORMAL)
            else:
                stdscr.addstr("SA: ", curses.A_NORMAL)
                stdscr.addstr(f"[ {sa_filter} ]", curses.A_NORMAL)
                
            stdscr.addstr("   ")
            
            # SN Field
            if focus_state == "SN":
                stdscr.addstr("SN: ", curses.A_BOLD)
                stdscr.addstr("[ ", curses.A_NORMAL)
                stdscr.addstr(sn_filter or " ", curses.A_REVERSE)
                stdscr.addstr(" ]", curses.A_NORMAL)
            else:
                stdscr.addstr("SN: ", curses.A_NORMAL)
                stdscr.addstr(f"[ {sn_filter} ]", curses.A_NORMAL)
        except curses.error:
            pass

        # Draw Separator (Row 2)
        try:
            stdscr.hline(2, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass

        # Draw Items (Row 3 onwards)
        if not filtered_with_indices:
            try:
                stdscr.addnstr(3, 2, "No items match the filters.", width - 3)
            except curses.error:
                pass
        else:
            end = min(len(filtered_with_indices), top + visible_rows)
            for row_offset, idx in enumerate(range(top, end)):
                row_idx = 3 + row_offset
                orig_idx, item = filtered_with_indices[idx]
                
                is_selected = (idx == current)
                prefix = "> " if is_selected else "  "
                text = prefix + str(item)
                
                try:
                    if is_selected:
                        if focus_state is None:
                            stdscr.addnstr(row_idx, 0, text, width - 1, curses.A_REVERSE)
                        else:
                            # Dim/normal highlight when focus is in the search bar
                            stdscr.addnstr(row_idx, 0, text, width - 1, dim_attr)
                    else:
                        stdscr.addnstr(row_idx, 0, text, width - 1)
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()

        # Keyboard event processing
        if key == 27:  # ESC
            return None
        
        elif key in (10, 13, curses.KEY_ENTER):
            if filtered_with_indices:
                return filtered_with_indices[current][0]
            
        elif key == curses.KEY_UP:
            if focus_state is None:
                if current > 0:
                    current -= 1
                else:
                    focus_state = "SA"  # Move up to search bar
            
        elif key == curses.KEY_DOWN:
            if focus_state is not None:
                focus_state = None  # Move down to list
                current = 0
            else:
                if current < len(filtered_with_indices) - 1:
                    current += 1
                    
        elif key == curses.KEY_LEFT:
            if focus_state == "SN":
                focus_state = "SA"
                
        elif key == curses.KEY_RIGHT:
            if focus_state == "SA":
                focus_state = "SN"
                
        elif key in (ord('s'), ord('S')):
            if focus_state is None:
                focus_state = "SA"
            else:
                if focus_state == "SA":
                    sa_filter += chr(key)
                # SN ignores non-digit inputs like s/S
                    
        elif key == curses.KEY_PPAGE:  # Page Up
            if focus_state is None:
                current = max(0, current - visible_rows)
                
        elif key == curses.KEY_NPAGE:  # Page Down
            if focus_state is None:
                current = min(len(filtered_with_indices) - 1, current + visible_rows) if filtered_with_indices else 0
                
        elif key == curses.KEY_HOME:
            if focus_state is None:
                current = 0
                
        elif key == curses.KEY_END:
            if focus_state is None:
                current = len(filtered_with_indices) - 1 if filtered_with_indices else 0
                
        elif key in (8, 127, curses.KEY_BACKSPACE, 263):
            if focus_state == "SA":
                sa_filter = sa_filter[:-1]
            elif focus_state == "SN":
                sn_filter = sn_filter[:-1]
                
        elif 32 <= key < 127:
            if focus_state == "SA":
                sa_filter += chr(key)
            elif focus_state == "SN":
                if chr(key).isdigit():
                    sn_filter += chr(key)

def main():
    args = parse_arguments()
    
    # Custom class to represent list items with SA and SN attributes
    class DemoItem:
        def __init__(self, sa, sn, description):
            self.sa = sa
            self.sn = sn
            self.description = description
            
        def __str__(self):
            return f"SA: {self.sa} | SN: {self.sn} | {self.description}"
            
    items = [
        DemoItem(f"App{i % 4}", f"{1000 + i}", f"Sample device item {i}")
        for i in range(1, 101)
    ]
    
    title_text = f"Use arrows/PgUp/PgDn/Home/End/Enter, Esc quits (Days: {args.days})"
    selected = curses.wrapper(select_menu, items, title_text, args.sa, args.sn)

    if selected is None:
        print("Quit without selection")
    else:
        print(f"Selected index={selected}, value={items[selected]}")

if __name__ == "__main__":
    main()
