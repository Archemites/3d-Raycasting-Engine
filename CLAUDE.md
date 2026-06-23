# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A **Python raycasting 3D engine** (Wolfenstein-style first-person renderer) built with:
- **pygame** for windowing/display
- **numpy** for vectorized raycasting and rendering
- **DDA (Digital Differential Analyzer)** ray-grid traversal for wall detection
- **Textured walls, floor/ceiling** with per-pixel lighting
- **3D solid boxes** (rendered face-by-face) and billboard sprites
- **Ambient occlusion** at wall/floor edges and concave corners
- **Multi-map teleport system** with E-key interaction and HUD prompt
- **Standalone pixel-art map editor** (`map_editor.py`)

## Running

```bash
# Run the game
python main.py

# Run the map editor
python map_editor.py

# No build step; all pure Python
```

### Game Controls

- **W/S/A/D** — Move/strafe
- **Left/Right arrows** — Rotate camera
- **Mouse X** — Turn (captured)
- **E** — Use portal (when near a door/teleport cell and prompt shows)
- **ESC** — Pause menu (quality slider, bob intensity slider)
- **F11** — Toggle fullscreen
- **Q** (paused) — Quit

### Performance Tuning

Quality is adjustable in-game via the pause menu slider (6 steps from 160×120 to 480×360). Hard-coded steps are in `main.py` `QUALITY_STEPS`. The internal buffer is upscaled to fill the window; 320×240 hits ~31 FPS on slow hardware.

## Architecture

### Rendering Pipeline (`render/renderer.py`)

Vectorized two-pass design — **not** per-column raycasting:

1. **Floor/ceiling** — entire screen cast as a 2D numpy block per row, transposed into buffer
2. **Walls** — lockstep DDA: all rays advance together; renders only the vertical band `draw_start..draw_end` (faixa optimization). Cell values `>= 1` stop the ray; `hit_type == 3` selects the door texture instead of wall texture.
3. **Boxes** — ray-segment intersection per face (back-face culled), Z-buffered
4. **Sprites** — billboard with Z-occlusion
5. **Blit** — `pygame.surfarray.blit_array()` to screen

Key performance wins: AO lightmap cached at map load (`_ao_lut`), lockstep DDA, faixa rendering, fixed-point math (uint16 multiply+shift), resolution scaling.

**Buffer layout:** `(sw, sh, 3)` uint8 RGB. Floor/ceiling outputs `(R, sw, 3)` then transposes to `(sw, R, 3)`. Walls/boxes write directly into `(sw, y_range, 3)`.

**AO:** Precomputed once per map load (`_ensure_ao_lut`): 32 samples per cell, 8 neighbors. At runtime: 1 LUT lookup per pixel. Wall AO = base gradient (bottom 14%) + corner check (diagonal neighbor). All AO checks use `>= 1` so door cells (value 3) cast shadows correctly.

### Map and Objects (`mapa/map.py`)

Cell values: `0` = floor, `1` = wall, `3` = teleport/door.

- `_DATA_<id>` — 2D list per map (A, B, C, ...)
- `_BOXES_<id>` — list of box dicts `{x, y, size, shape, tex_index}` per map
- `TELEPORT_TABLE` — `{(map_id, gx, gy): (dest_map_id, dgx, dgy)}`

`Map.__init__` uses `sys.modules[__name__].__dict__` to dynamically look up `_DATA_<id>` and `_BOXES_<id>` so new maps added by the editor are picked up automatically without modifying the class.

`Map.near_teleport(px, py, radius=1.2)` — scans nearby cells for value `3`, checks `TELEPORT_TABLE`.  
`Map.resolve_spawn(dest_map_id, tp_gx, tp_gy)` — walks N→S→W→E cardinal neighbors of the destination portal for the first empty cell (value `0`); returns `(Map, spawn_x, spawn_y)`.

### Boxes (`obj/box.py`)

`Box(x, y, size, tex_index)` — axis-aligned cube. `faces()` returns 4 tuples `(ax, ay, bx, by, nx, ny)`. The renderer does ray-segment intersection per face.

In `main.py`, boxes are loaded from `game_map.boxes` (the `_BOXES_<id>` list) via `_boxes_from_map()`. If the list is empty, 4 hardcoded default boxes are used as fallback. On teleport, `_boxes_from_map()` is called again with the new map.

### Control Flow (`main.py`)

```
init → Map("A"), Player, _boxes_from_map(), Renderer
loop:
  events: WASD/mouse move, E-key teleport, ESC pause, F11 fullscreen
  if not paused:
    move player (AABB collision vs walls and boxes)
    tp_cooldown countdown; near_tp = game_map.near_teleport(...)
    renderer.frame(game_map, player, boxes, bob)
  scale render_surf → screen rect (letterboxed)
  if near_tp and not paused: draw [E] Interagir HUD
  if paused: draw pause overlay with sliders
```

Teleport flow: `K_e` → `Map.resolve_spawn` → update `game_map`, `player.x/y`, `boxes`, reset `renderer._ao_lut = None` (forces AO recompute), set `tp_cooldown = 60`.

### Map Editor (`map_editor.py`)

Standalone tool. Layout: left texture panel (220px) | canvas | right panel (270px), with toolbar and tab bar.

**Reading/writing `mapa/map.py`:** Uses `ast.parse` + `ast.literal_eval` to safely extract `_DATA_*`, `_BOXES_*`, and `TELEPORT_TABLE`. Writes back by regenerating those sections and copying the `class Map` block verbatim from the existing file.

**Tools:** Floor `[1]`, Wall `[2]`, Door `[3]`, Box `[4]`, Rectangle `[5]`, Circle `[6]`.  
- Rectangle and Circle: click-drag defines bounding box; preview shown live; cells filled on mouse-up.
- Box tool: click empty cell → places `BoxObj`; click existing box → drag to reposition. Size (0.1–2.0) and shape (square/circle) set in right panel. `Delete` removes selected box.

**Left panel:** Per-slot texture preview (56×56). Import copies a file into `textures/` and reloads; Export copies the current file to a target path. Toggle **Textura ON/OFF** switches grid cells between texture preview and solid colors.

**Right panel:** Tool selector, rect/circle fill value, new-box config, selected-box editor, door linking UI (bidirectional `TELEPORT_TABLE` entries), grid resize, zoom.

**Undo:** 80-level stack; snapshots `(maps, tp, boxes_raw)` via `copy.deepcopy`.

**State persistence:** `EditorState.save()` calls `_save_map_file(maps, tp, boxes_raw)`.

## Technical Notes

### DDA and Door Cells

The DDA loop stops on `cell >= 1` (walls and doors). After the wall draw, door columns are overridden vectorially using `hit_type == 3` mask — no per-column loop.

### Texture Coordinates

- **Walls/doors:** U (0–1) along wall edge; V from bottom to top
- **Floor/ceiling:** Tiled repeat, modulo tile size
- **Boxes:** Per-face UV; V=0 ceiling, V=1 floor for each face

### Collision (AABB)

```python
def blocked(x, y):
    if game_map.get(int(x), int(y)) != 0: return True  # walls AND door cells block
    for box in boxes:
        s = box.size / 2 + 0.2
        if abs(x - box.x) < s and abs(y - box.y) < s: return True
    return False
```

Door cells (value 3) block movement — the player must use the portal rather than walk through.

## Debugging Tips

- **Slow render?** Time each pass: floor_ceiling, walls, boxes, blit
- **Visual glitches?** Check `_zbuf` — should increase monotonically with distance
- **AO not rendering?** Confirm `_ao_lut` is not None; check map has walls nearby
- **Teleport not firing?** Check `TELEPORT_TABLE` has the matching `(map_id, gx, gy)` key
- **Boxes missing after teleport?** `_boxes_from_map()` must be called with the new map; check `_BOXES_<id>` is present in map.py
- **Memory bloat?** `_ao_lut` is `(mh*32, mw*32)` floats; for large maps reduce `_ao_S` or compute on-demand
