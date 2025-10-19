# Instructions for this repo

This repository is a MicroPython port of classic Tetris targeting the Pimoroni Explorer (and eventually Badger hardware). The code runs on-device and uses PicoGraphics for rendering and GPIO buttons for input.

## Architecture overview

- Entry point: `main.py`
  - Game loop with `setup()` and `loop()` methods inside a `Tetris` class.
  - Game state encapsulated in the `Tetris` class instance: `current`, `next_piece`, `blocks`, `score`, `rows`, `lost`, etc.
  - Core helpers (methods of `Tetris` class):
    - Board/pieces: `each_block`, `occupied`, `unoccupied`, `random_piece`
    - Game control: `move`, `rotate`, `drop`, `drop_piece`, `remove_lines`, `remove_line`, `reset`
    - Scoring/rows: `set_score`, `add_score`, `set_rows`, `add_rows`, `set_visual_score`, `clear_score`, `clear_rows`
    - Grid access: `get_block`, `set_block`, `clear_blocks`
    - Rendering: `draw`, `draw_court`, `draw_next`, `draw_score`, `draw_piece`, `draw_block`
    - Input handling: `on_left_button`, `on_right_button`, `on_rotate_button` (uses global `debounce` function)
- Hardware abstraction: `lib/explorer.py`
  - Exposes `display` (PicoGraphics), button Pins (`button_a`, `button_b`, `button_c`, `button_x`, `button_y`, `button_z`, `button_user`), and color constants `BLACK`, `WHITE` plus other colors used by the game.
  - Also includes servo, audio helpers, and other hardware abstractions not currently used by the game.

## Key conventions and patterns

- Snake case for functions and variables throughout `main.py`.
- Object-oriented design with game state encapsulated in a `Tetris` class. The game creates a single instance `_game` and runs it in a simple main loop.
- The playfield is an `nx` by `ny` grid (15x15). `blocks[x][y]` holds either `None` or a piece type dict (`i, j, l, o, s, t, z`).
- Piece rotation uses 16-bit bitmasks in `type["blocks"][dir]` and is iterated via `each_block`.

## Developer workflows

- Running on device: copy files to device filesystem (e.g., `main.py` at root, and `lib/*` under `lib/`). Device auto-runs `main.py`.
- Desktop execution: This repo imports MicroPython-only modules in `lib/explorer.py`. For local syntax checks, set `PYTHONPATH=lib` and note that imports like `machine`, `micropython`, `picographics` will not resolve unless stubbed. Ruff/Pylance warnings are expected on desktop.
- No test suite is present. If adding tests, isolate hardware-bound code behind light wrappers or flags.

## Rendering and input specifics

- Display size is derived via `display.get_bounds()`, and block size computed as:
  - `dx = (0.6 * WIDTH) / nx`
  - `dy = (0.75 * HEIGHT) / ny`
- Court rendering offsets the playfield by `+6` blocks on X to make room for next-piece/score.
- Buttons used:
  - Left: `button_c`
  - Right: `button_z`
  - Rotate: `button_y`
- Debounce logic is adapted from Pimoroni Explorer example and uses `time.ticks_ms()` with a module-scoped `last_button_press`.

## Adding features safely

- Keep function naming and call sites in snake_case.
- When changing rendering, update `draw_*` functions and ensure `display.update()` remains the last step in `draw()`.
- When introducing new inputs or animations, reuse `debounce` pattern and avoid blocking sleeps in the main loop except for post-lose pause.
- If refactoring globals, do it incrementally: first encapsulate score/rows, then piece state, verifying `move`, `drop`, and `occupied` continue to work.

## External dependencies and environment

- MicroPython on RP2350-compatible board (Pimoroni Explorer).
- PicoGraphics and Pimoroni libraries (imported in `lib/explorer.py`). These are not pip-installable for desktop; use stubs or ignore diagnostics in editors.

## Examples from code

- Iterate a piece shape across the grid:
  - `each_block(piece_type, x, y, dir, lambda bx, by: set_block(bx, by, piece_type))`
- Check placement before moving/rotating:
  - `if unoccupied(current["type"], new_x, new_y, new_dir): ...`
- Line removal and scoring:
  - `remove_lines()` scans from bottom up; after `n` lines: `add_rows(n)` and `add_score(100 * 2 ** (n - 1))`.

## Agent tips

- Respect MicroPython constraints (no heavy libs, keep memory use modest).
- Don’t reorder hardware imports—`from explorer import ...` is deliberate to centralize device specifics.
- If you need to silence desktop-only import warnings, prefer editor config or per-file ignore; do not alter runtime behavior for device.
