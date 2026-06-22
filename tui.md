# Terminal User Interface Menu (TUI)
- name: tui.py
- execute: python tui.py
- description: A lightweight, scrollable terminal-based selection menu using the standard library `curses` module.

## tech stack
- Python 3.10
- Python standard library `curses` module (no external dependencies)

## input
- `items`: A list of objects/strings to display as options.
- `title` (optional): A header title displayed at the top of the menu screen.

## output
- The index of the selected item (integer), or `None` if the selection is aborted.

## requirement
- Render an interactive terminal menu using curses.
- Support key navigation:
  - `KEY_UP` (Up Arrow): Move highlight up by one item.
  - `KEY_DOWN` (Down Arrow): Move highlight down by one item.
  - `KEY_PPAGE` (Page Up): Scroll selection up by one full screen page.
  - `KEY_NPAGE` (Page Down): Scroll selection down by one full screen page.
  - `KEY_HOME` (Home): Jump selection to the first item.
  - `KEY_END` (End): Jump selection to the last item.
  - `Enter` / `10` / `13` (Enter): Select the current item and exit.
  - `Esc` / `27` (Escape): Abort selection and exit.
- Scrollable list behavior when the number of items exceeds the visible screen height.
- Auto-adaptation to terminal size, ensuring no overflows/crashes by clamping strings to the terminal width using `addnstr`.

## example
- Run the demo menu showcasing scrolling and selections:
  ```bash
  python tui.py
  ```

## tests
- There are currently no automated unit tests for `tui.py` due to the interactive nature of `curses`.

## reference
- tui.py
