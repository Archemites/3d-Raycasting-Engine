"""
Editor de mapas pixel-art para o raycaster.

Uso:
    python map_editor.py

Controles:
    Botão esquerdo  — pintar / arrastar forma
    Botão direito   — apagar (vira chão = 0)
    1 / F           — ferramenta Chão
    2 / W           — ferramenta Parede
    3 / D           — ferramenta Porta/Teleporte
    4               — ferramenta Caixa (Box)
    5               — ferramenta Retângulo
    6               — ferramenta Círculo
    Ctrl+S          — salvar
    Ctrl+Z          — desfazer
    Scroll          — zoom
    Botão do meio   — pan
"""

import ast
import copy
import math
import os
import shutil
import sys
import textwrap

import pygame

# tkinter para diálogo de arquivo nativo (opcional — ignora silenciosamente se ausente)
try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
    _TK_ROOT = None

    def _tk_root():
        global _TK_ROOT
        if _TK_ROOT is None:
            _TK_ROOT = tk.Tk()
            _TK_ROOT.withdraw()
        return _TK_ROOT

    def open_file_dialog(title="Abrir arquivo", filetypes=None):
        root = _tk_root()
        filetypes = filetypes or [("Imagens PNG", "*.png"), ("Todos os arquivos", "*.*")]
        path = tk_filedialog.askopenfilename(parent=root, title=title, filetypes=filetypes)
        return path or ""

    def save_file_dialog(title="Salvar arquivo", filetypes=None, initialfile=""):
        root = _tk_root()
        filetypes = filetypes or [("Imagens PNG", "*.png"), ("Todos os arquivos", "*.*")]
        path = tk_filedialog.asksaveasfilename(parent=root, title=title,
                                               filetypes=filetypes,
                                               defaultextension=".png",
                                               initialfile=initialfile)
        return path or ""

    HAS_TK = True
except Exception:
    HAS_TK = False
    def open_file_dialog(title="", filetypes=None): return ""
    def save_file_dialog(title="", filetypes=None, initialfile=""): return ""

# ---------------------------------------------------------------------------
# Constantes de layout
# ---------------------------------------------------------------------------

WIN_W, WIN_H  = 1280, 820
TOOLBAR_H     = 44
TABBAR_H      = 36
LEFT_W        = 240       # painel esquerdo (paleta de texturas)
PANEL_W       = 270       # painel direito
STATUS_H      = 28

CELL_MIN = 10
CELL_MAX = 64
CELL_DEF = 32

# Ferramentas
TOOL_FLOOR  = 0
TOOL_WALL   = 1
TOOL_DOOR   = 3
TOOL_BOX    = 4
TOOL_RECT   = 5
TOOL_CIRCLE = 6

# ---------------------------------------------------------------------------
# Codificação de células com textura
#
# Células de parede carregam o índice do brush na paleta:
#   cell = 10000 + letra_idx * 100 + num
#   letra_idx = 0..25 (A..Z), num = 1..99
#   Código legível para o usuário: "1A", "14A", "1B", "99Z" etc.
#   cell == 1  → parede legada (textura padrão, índice 0 da paleta)
# ---------------------------------------------------------------------------

def cell_to_wall_code(cell: int) -> str:
    """Converte valor de célula para código legível, ex: 10014 → '14A'."""
    if cell < 10000:
        return "1A"
    code      = cell - 10000
    letra_idx = code // 100
    num       = code % 100
    letra     = chr(ord('A') + min(letra_idx, 25))
    return f"{num}{letra}"


def wall_code_to_cell(num: int, letra: str) -> int:
    """Converte (num, letra) para valor de célula, ex: (14, 'A') → 10014."""
    letra_idx = ord(letra.upper()) - ord('A')
    return 10000 + letra_idx * 100 + num


def brush_registry_to_cell(brush_position: int) -> int:
    """
    Converte a posição do brush na lista de wall brushes (0-based) para
    o valor de célula correspondente.
    Posição 0 → código '1A' → cell 10001
    Posição 98 → código '99A' → cell 10099
    Posição 99 → código '1B' → cell 10101
    """
    letra_idx = brush_position // 99
    num       = brush_position % 99 + 1
    return wall_code_to_cell(num, chr(ord('A') + min(letra_idx, 25)))


def cell_to_brush_position(cell: int) -> int:
    """Inverso de brush_registry_to_cell."""
    if cell < 10000:
        return 0
    code      = cell - 10000
    letra_idx = code // 100
    num       = code % 100
    return letra_idx * 99 + (num - 1)


def is_wall_cell(cell: int) -> bool:
    return cell == 1 or cell >= 10000


# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------

COL_BG        = (28, 28, 30)
COL_EMPTY     = (18, 18, 20)
COL_WALL      = (60, 160, 60)
COL_WALL_LIT  = (90, 210, 90)
COL_DOOR      = (200, 50, 50)
COL_DOOR_LIT  = (255, 90, 90)
COL_BOX_FILL  = (180, 130, 60)
COL_BOX_LIT   = (220, 170, 90)
COL_GRID      = (45, 45, 50)
COL_GRID_HI   = (80, 80, 90)
COL_TOOLBAR   = (38, 38, 42)
COL_TABBAR    = (32, 32, 36)
COL_TAB_ACT   = (58, 58, 65)
COL_TAB_HOV   = (48, 48, 55)
COL_PANEL     = (36, 36, 40)
COL_LEFT      = (32, 32, 38)
COL_BTN       = (55, 55, 62)
COL_BTN_HOV   = (75, 75, 85)
COL_BTN_ACT   = (90, 130, 200)
COL_TEXT      = (210, 210, 215)
COL_TEXT_DIM  = (130, 130, 140)
COL_ACCENT    = (80, 160, 255)
COL_DANGER    = (200, 60, 60)
COL_STATUS_BG = (24, 24, 28)

MAP_FILE = os.path.join(os.path.dirname(__file__), "mapa", "map.py")
TEX_DIR  = os.path.join(os.path.dirname(__file__), "textures")

# ---------------------------------------------------------------------------
# Leitura / escrita do map.py
# ---------------------------------------------------------------------------

def _cell_str_to_int(v) -> int:
    """Converte um valor de célula do arquivo para inteiro interno.
    Strings como '1A', '14B' viram o inteiro codificado correspondente.
    Inteiros passam direto."""
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s and s[-1].isalpha() and s[:-1].isdigit():
            num   = int(s[:-1])
            letra = s[-1].upper()
            return wall_code_to_cell(num, letra)
    return int(v)


def _decode_map_rows(raw_rows) -> list:
    """Converte linhas brutas (listas com ints ou strings) para listas de ints."""
    return [[_cell_str_to_int(v) for v in row] for row in raw_rows]


def _load_map_file():
    """Lê map.py. Retorna (maps_dict, teleport_table, boxes_dict)."""
    with open(MAP_FILE, "r", encoding="utf-8") as f:
        src = f.read()

    tree   = ast.parse(src)
    maps   = {}
    tptab  = {}
    boxes  = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id

            if name.startswith("_DATA_"):
                mid = name[len("_DATA_"):]
                raw = ast.literal_eval(node.value)
                maps[mid] = _decode_map_rows(raw)

            if name == "TELEPORT_TABLE":
                raw = ast.literal_eval(node.value)
                for k, v in raw.items():
                    tptab[k] = v

            if name.startswith("_BOXES_"):
                mid = name[len("_BOXES_"):]
                boxes[mid] = ast.literal_eval(node.value)

    for mid in maps:
        boxes.setdefault(mid, [])

    return maps, tptab, boxes


def _encode_row(row: list) -> str:
    """Serializa uma linha do mapa: ints >= 10000 viram strings '1A', '2B' etc."""
    parts = []
    for v in row:
        if isinstance(v, int) and v >= 10000:
            parts.append(repr(cell_to_wall_code(v)))
        else:
            parts.append(str(v))
    return "[" + ", ".join(parts) + "]"


def _save_map_file(maps_dict, teleport_table, boxes_dict):
    """Reescreve map.py preservando o bloco de classe."""

    lines = [
        "# Valores de célula:",
        "#   0     = chão",
        "#   1     = parede (textura padrão)",
        "#   3     = teleporte (spawna o jogador no destino configurado)",
        "#   '1A'  = parede com textura brush 1A  (num=1, letra=A)",
        "#   '14B' = parede com textura brush 14B (num=14, letra=B)",
        "",
    ]

    for mid, data in maps_dict.items():
        lines.append(f"_DATA_{mid} = [")
        for row in data:
            lines.append("    " + _encode_row(row) + ",")
        lines.append("]")
        lines.append("")

    for mid, blist in boxes_dict.items():
        lines.append(f"_BOXES_{mid} = {blist!r}")
        lines.append("")

    lines.append("# Tabela de teleportes:")
    lines.append("#   chave  = (map_id, grid_x, grid_y)")
    lines.append("#   valor  = (dest_map_id, dest_tp_gx, dest_tp_gy)")
    lines.append("# O spawn exato é calculado em runtime.")
    lines.append("TELEPORT_TABLE = {")
    for (mid, gx, gy), (dmid, dgx, dgy) in teleport_table.items():
        lines.append(f'    ("{mid}", {gx:2d}, {gy:2d}): ("{dmid}", {dgx:2d}, {dgy:2d}),')
    lines.append("}")
    lines.append("")

    # Função auxiliar embutida no arquivo gerado para que Map() possa decodificar strings
    lines.append(textwrap.dedent("""\
        def _cell_to_int(v) -> int:
            if isinstance(v, int):
                return v
            s = str(v).strip()
            if s and s[-1].isalpha() and s[:-1].isdigit():
                num       = int(s[:-1])
                letra_idx = ord(s[-1].upper()) - ord('A')
                return 10000 + letra_idx * 100 + num
            return int(v)
        """))

    with open(MAP_FILE, "r", encoding="utf-8") as f:
        original = f.read()
    class_start = original.find("\nclass Map")
    if class_start != -1:
        lines.append(original[class_start + 1:].rstrip())
    else:
        lines.append(textwrap.dedent("""\
            class Map:
                def __init__(self, map_id: str = "A"):
                    import sys
                    g = sys.modules[__name__].__dict__
                    self.map_id = map_id
                    self._data  = g.get(f"_DATA_{map_id}", [[]])
                    self.width  = len(self._data[0]) if self._data else 0
                    self.height = len(self._data)

                def get(self, x, y):
                    if x < 0 or x >= self.width or y < 0 or y >= self.height:
                        return 1
                    return self._data[y][x]
        """))

    with open(MAP_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Gerenciamento de texturas — paleta de brushes
# ---------------------------------------------------------------------------

# Categorias de brush que o jogo conhece
BRUSH_CATEGORIES = ("wall", "floor", "door", "box")

# Arquivo que persiste a lista de brushes importados entre sessões
BRUSH_REGISTRY = os.path.join(TEX_DIR, "_brushes.txt")

# Texturas padrão por categoria
_DEFAULT_PATHS = {
    "wall":  os.path.join(TEX_DIR, "wall.png"),
    "floor": os.path.join(TEX_DIR, "floor.png"),
    "door":  os.path.join(TEX_DIR, "door.png"),
    "box":   os.path.join(TEX_DIR, "box.png"),
}


class BrushEntry:
    """Um brush na paleta: caminho + categoria + surface carregada."""
    def __init__(self, path: str, category: str):
        self.path     = path
        self.category = category   # "wall" | "floor" | "door" | "box"
        self.surface: pygame.Surface | None = None

    def load(self):
        try:
            self.surface = pygame.image.load(self.path).convert()
        except Exception:
            self.surface = None

    def preview(self, size: int) -> pygame.Surface | None:
        if self.surface is None:
            return None
        return pygame.transform.scale(self.surface, (size, size))

    def __repr__(self):
        return f"BrushEntry({self.category!r}, {self.path!r})"


class TextureManager:
    """
    Paleta de brushes no estilo Photoshop.

    Cada brush é um arquivo PNG associado a uma categoria (wall/floor/door/box).
    O brush ativo por categoria define qual textura é usada no jogo e na grade.
    """

    def __init__(self):
        self.brushes: list[BrushEntry] = []
        # índice do brush ativo por categoria
        self.active: dict[str, int] = {c: -1 for c in BRUSH_CATEGORIES}
        self._preview_cache: dict[tuple, pygame.Surface | None] = {}
        self._load_registry()

    # ---- persistência -------------------------------------------------------

    def _load_registry(self):
        """Carrega brushes do arquivo de registro e garante os padrões."""
        loaded_paths = set()

        if os.path.isfile(BRUSH_REGISTRY):
            try:
                with open(BRUSH_REGISTRY, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if not line or line.startswith("#"):
                            continue
                        # formato: [*| ]category|path
                        is_active = line.startswith("*")
                        rest = line[1:] if line[0] in ("*", " ") else line
                        parts = rest.split("|", 1)
                        if len(parts) == 2:
                            cat, path = parts[0].strip(), parts[1].strip()
                            if cat in BRUSH_CATEGORIES and os.path.isfile(path):
                                idx = self._add_brush(path, cat, save=False)
                                loaded_paths.add(os.path.abspath(path))
                                if is_active:
                                    self.active[cat] = idx
            except Exception:
                pass

        # garante brush padrão para cada categoria
        for cat, default_path in _DEFAULT_PATHS.items():
            if os.path.isfile(default_path):
                abs_dp = os.path.abspath(default_path)
                if abs_dp not in loaded_paths:
                    self._add_brush(default_path, cat, save=False)

        # para categorias sem ativo marcado, usa o primeiro disponível
        for cat in BRUSH_CATEGORIES:
            if self.active[cat] < 0:
                for i, b in enumerate(self.brushes):
                    if b.category == cat:
                        self.active[cat] = i
                        break

        self._save_registry()

    def _save_registry(self):
        try:
            os.makedirs(TEX_DIR, exist_ok=True)
            with open(BRUSH_REGISTRY, "w", encoding="utf-8") as f:
                f.write("# brush_category | absolute_path  (* = ativo)\n")
                for i, b in enumerate(self.brushes):
                    marker = "*" if self.active.get(b.category) == i else " "
                    f.write(f"{marker}{b.category}|{b.path}\n")
        except Exception:
            pass

    # ---- operações de paleta ------------------------------------------------

    def _add_brush(self, path: str, category: str, save: bool = True) -> int:
        """Adiciona brush e retorna seu índice. Ignora duplicatas."""
        abs_path = os.path.abspath(path)
        for i, b in enumerate(self.brushes):
            if os.path.abspath(b.path) == abs_path:
                return i
        entry = BrushEntry(abs_path, category)
        entry.load()
        self.brushes.append(entry)
        idx = len(self.brushes) - 1
        if self.active.get(category, -1) < 0:
            self.active[category] = idx
        if save:
            self._save_registry()
            self._preview_cache.clear()
        return idx

    def import_brush(self, src_path: str, category: str) -> int:
        """Copia arquivo para textures/ se necessário, registra e ativa."""
        dest = os.path.join(TEX_DIR, os.path.basename(src_path))
        try:
            same = os.path.samefile(src_path, dest)
        except OSError:
            same = False
        if not same:
            shutil.copy2(src_path, dest)
        idx = self._add_brush(dest, category, save=True)
        self.active[category] = idx
        self._preview_cache.clear()
        return idx

    def remove_brush(self, idx: int):
        """Remove brush da paleta (não apaga o arquivo)."""
        if not (0 <= idx < len(self.brushes)):
            return
        cat = self.brushes[idx].category
        self.brushes.pop(idx)
        self._preview_cache.clear()
        # reajusta índices ativos
        for c in BRUSH_CATEGORIES:
            if self.active[c] == idx:
                self.active[c] = -1
            elif self.active[c] > idx:
                self.active[c] -= 1
        # garante ativo válido
        if self.active[cat] < 0:
            for i, b in enumerate(self.brushes):
                if b.category == cat:
                    self.active[cat] = i
                    break
        self._save_registry()

    def set_active(self, idx: int):
        if 0 <= idx < len(self.brushes):
            cat = self.brushes[idx].category
            self.active[cat] = idx
            self._preview_cache.clear()
            self._save_registry()

    def brushes_of(self, category: str) -> list[tuple[int, BrushEntry]]:
        return [(i, b) for i, b in enumerate(self.brushes) if b.category == category]

    # ---- acesso por slot (compatibilidade com o resto do código) ------------

    def get_preview(self, slot: str, size: int) -> pygame.Surface | None:
        key = (slot, size)
        if key not in self._preview_cache:
            idx = self.active.get(slot, -1)
            if 0 <= idx < len(self.brushes):
                self._preview_cache[key] = self.brushes[idx].preview(size)
            else:
                self._preview_cache[key] = None
        return self._preview_cache[key]

    def get_cell_preview(self, slot: str, cell_px: int) -> pygame.Surface | None:
        return self.get_preview(slot, cell_px)

    # caminho do brush ativo (para exportar)
    def active_path(self, slot: str) -> str:
        idx = self.active.get(slot, -1)
        if 0 <= idx < len(self.brushes):
            return self.brushes[idx].path
        return ""

    def wall_brush_position(self, global_idx: int) -> int:
        """Posição 0-based deste brush na lista de brushes wall (ordem do registro)."""
        pos = 0
        for i, b in enumerate(self.brushes):
            if b.category == "wall":
                if i == global_idx:
                    return pos
                pos += 1
        return 0

    def active_wall_cell(self) -> int:
        """Valor de célula correspondente ao brush wall atualmente ativo."""
        idx = self.active.get("wall", -1)
        if idx < 0:
            return 1
        pos = self.wall_brush_position(idx)
        return brush_registry_to_cell(pos)

    def preview_for_cell(self, cell: int, size: int) -> pygame.Surface | None:
        """Retorna preview do brush correspondente ao valor de célula.
        Células val==1 (legadas) sempre usam o brush da posição 0, não o ativo."""
        if not is_wall_cell(cell):
            return self.get_preview("floor" if cell == 0 else "door", size)
        pos = cell_to_brush_position(cell) if cell >= 10000 else 0
        wall_brushes = [(i, b) for i, b in enumerate(self.brushes) if b.category == "wall"]
        if pos < len(wall_brushes):
            global_idx, brush = wall_brushes[pos]
            key = ("cell_pos", pos, size)
            if key not in self._preview_cache:
                self._preview_cache[key] = brush.preview(size)
            return self._preview_cache[key]
        return self.get_preview("wall", size)


# ---------------------------------------------------------------------------
# Estado do editor
# ---------------------------------------------------------------------------

class BoxObj:
    def __init__(self, x: float, y: float, size: float = 0.5, shape: str = "square",
                 tex_index: int = 0):
        self.x         = x
        self.y         = y
        self.size      = size
        self.shape     = shape
        self.tex_index = tex_index

    def to_dict(self):
        return {"x": self.x, "y": self.y, "size": self.size,
                "shape": self.shape, "tex_index": self.tex_index}

    @staticmethod
    def from_dict(d):
        return BoxObj(d["x"], d["y"], d.get("size", 0.5),
                      d.get("shape", "square"), d.get("tex_index", 0))


class EditorState:
    DEFAULT_SIZE = (16, 16)

    def __init__(self):
        self.maps, self.tp, self._boxes_raw = _load_map_file()
        if not self.maps:
            self.maps["A"] = self._blank(*self.DEFAULT_SIZE)
        self.map_ids = list(self.maps.keys())
        self.active  = self.map_ids[0]

        self.boxes: dict[str, list[BoxObj]] = {
            mid: [BoxObj.from_dict(d) for d in lst]
            for mid, lst in self._boxes_raw.items()
        }
        for mid in self.maps:
            self.boxes.setdefault(mid, [])

        self.tool       = TOOL_WALL
        self.cell_px    = CELL_DEF
        self.offset     = [0, 0]
        self.undo_stack: list = []

        self.sel_door   = None
        self.sel_box: int | None = None

        self.renaming   = None
        self.rename_buf = ""
        self.painting   = False

        self.shape_start: tuple[int, int] | None = None
        self.shape_preview: list[tuple[int, int]] = []

        self.new_box_size  = 0.5
        self.new_box_shape = "square"

        self.fill_val = 1

        self.show_texture = True

        # paleta: categoria selecionada na UI do painel esquerdo
        self.palette_cat: str = "wall"

    # ---- helpers -----------------------------------------------------------

    def _blank(self, w, h):
        return [[0] * w for _ in range(h)]

    def current(self):
        return self.maps[self.active]

    def rows(self): return len(self.current())
    def cols(self): return len(self.current()[0]) if self.current() else 0

    def current_boxes(self) -> list[BoxObj]:
        return self.boxes.setdefault(self.active, [])

    def snapshot(self):
        boxes_raw = {mid: [b.to_dict() for b in lst]
                     for mid, lst in self.boxes.items()}
        self.undo_stack.append((
            copy.deepcopy(self.maps),
            copy.deepcopy(self.tp),
            copy.deepcopy(boxes_raw),
        ))
        if len(self.undo_stack) > 80:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            m, t, br = self.undo_stack.pop()
            self.maps = m
            self.tp   = t
            self.boxes = {mid: [BoxObj.from_dict(d) for d in lst]
                          for mid, lst in br.items()}
            if self.active not in self.maps:
                self.active = list(self.maps.keys())[0]

    def set_cell(self, gx, gy, val):
        data = self.current()
        if 0 <= gy < len(data) and 0 <= gx < len(data[0]):
            if data[gy][gx] != val:
                data[gy][gx] = val
                if val != 3:
                    self.tp.pop((self.active, gx, gy), None)
                    dead = [k for k, v in self.tp.items()
                            if v == (self.active, gx, gy)]
                    for k in dead:
                        del self.tp[k]

    def _cell_value(self, tex_mgr=None):
        if self.tool == TOOL_FLOOR:  return 0
        if self.tool == TOOL_WALL:
            return tex_mgr.active_wall_cell() if tex_mgr else 1
        if self.tool == TOOL_DOOR:   return 3
        if self.tool in (TOOL_RECT, TOOL_CIRCLE):
            if self.fill_val == 1 and tex_mgr:
                return tex_mgr.active_wall_cell()
            return self.fill_val
        return 0

    # ---- shape tools -------------------------------------------------------

    def cells_rect(self, gx0, gy0, gx1, gy1) -> list[tuple[int, int]]:
        x0, x1 = min(gx0, gx1), max(gx0, gx1)
        y0, y1 = min(gy0, gy1), max(gy0, gy1)
        return [(gx, gy) for gy in range(y0, y1 + 1)
                          for gx in range(x0, x1 + 1)]

    def cells_circle(self, gx0, gy0, gx1, gy1) -> list[tuple[int, int]]:
        cx = (gx0 + gx1) / 2
        cy = (gy0 + gy1) / 2
        rx = abs(gx1 - gx0) / 2 + 0.5
        ry = abs(gy1 - gy0) / 2 + 0.5
        cols, rows = self.cols(), self.rows()
        out = []
        for gy in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for gx in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if 0 <= gx < cols and 0 <= gy < rows:
                    if rx > 0 and ry > 0:
                        nx = (gx + 0.5 - cx) / rx
                        ny = (gy + 0.5 - cy) / ry
                        if nx * nx + ny * ny <= 1.0:
                            out.append((gx, gy))
        return out

    def apply_shape(self, gx0, gy0, gx1, gy1, tex_mgr=None):
        val = self._cell_value(tex_mgr)
        if self.tool == TOOL_RECT:
            cells = self.cells_rect(gx0, gy0, gx1, gy1)
        else:
            cells = self.cells_circle(gx0, gy0, gx1, gy1)
        for gx, gy in cells:
            self.set_cell(gx, gy, val)

    # ---- box helpers -------------------------------------------------------

    def add_box(self, gx: int, gy: int):
        bx = BoxObj(gx + 0.5, gy + 0.5, self.new_box_size, self.new_box_shape)
        self.current_boxes().append(bx)
        self.sel_box = len(self.current_boxes()) - 1

    def remove_selected_box(self):
        blist = self.current_boxes()
        if self.sel_box is not None and 0 <= self.sel_box < len(blist):
            blist.pop(self.sel_box)
            self.sel_box = None

    def box_at(self, gx: int, gy: int) -> int | None:
        for i, b in enumerate(self.current_boxes()):
            if int(b.x) == gx and int(b.y) == gy:
                return i
        return None

    # ---- map management ---------------------------------------------------

    def add_map(self, mid, w=16, h=16):
        if mid and mid not in self.maps:
            self.maps[mid] = self._blank(w, h)
            self.boxes[mid] = []
            self.map_ids = list(self.maps.keys())
            self.active  = mid

    def delete_map(self, mid):
        if len(self.maps) <= 1:
            return
        del self.maps[mid]
        self.boxes.pop(mid, None)
        dead = [k for k in self.tp if k[0] == mid or self.tp[k][0] == mid]
        for k in dead:
            del self.tp[k]
        self.map_ids = list(self.maps.keys())
        if self.active == mid:
            self.active = self.map_ids[0]

    def rename_map(self, old, new):
        if not new or new == old or new in self.maps:
            return
        self.maps[new] = self.maps.pop(old)
        self.boxes[new] = self.boxes.pop(old, [])
        new_tp = {}
        for (mid, gx, gy), (dmid, dgx, dgy) in self.tp.items():
            k = (new if mid  == old else mid,  gx, gy)
            v = (new if dmid == old else dmid, dgx, dgy)
            new_tp[k] = v
        self.tp = new_tp
        self.map_ids = list(self.maps.keys())
        self.active  = new

    def screen_to_grid(self, mx, my, grid_rect):
        gx = int((mx - grid_rect.x) // self.cell_px)
        gy = int((my - grid_rect.y) // self.cell_px)
        return gx, gy

    def grid_rect(self, canvas_rect):
        w = self.cols() * self.cell_px
        h = self.rows() * self.cell_px
        x = canvas_rect.x + self.offset[0]
        y = canvas_rect.y + self.offset[1]
        return pygame.Rect(x, y, w, h)

    def save(self):
        boxes_raw = {mid: [b.to_dict() for b in lst]
                     for mid, lst in self.boxes.items()}
        _save_map_file(self.maps, self.tp, boxes_raw)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

def draw_text(surf, text, x, y, font, color=COL_TEXT, anchor="topleft"):
    s = font.render(text, True, color)
    r = s.get_rect(**{anchor: (x, y)})
    surf.blit(s, r)
    return r


def draw_button(surf, rect, label, font, hover=False, active=False, danger=False):
    col = COL_DANGER if danger else (COL_BTN_ACT if active else
                                     (COL_BTN_HOV if hover else COL_BTN))
    pygame.draw.rect(surf, col, rect, border_radius=5)
    pygame.draw.rect(surf, (80, 80, 90), rect, 1, border_radius=5)
    draw_text(surf, label, rect.centerx, rect.centery, font, anchor="center")
    return rect


def draw_tool_btn(surf, rect, label, color_swatch, font, active=False, hover=False):
    bg = COL_BTN_ACT if active else (COL_BTN_HOV if hover else COL_BTN)
    pygame.draw.rect(surf, bg, rect, border_radius=5)
    pygame.draw.rect(surf, (80, 80, 90), rect, 1, border_radius=5)
    sw = 12
    swatch = pygame.Rect(rect.x + 6, rect.centery - sw // 2, sw, sw)
    pygame.draw.rect(surf, color_swatch, swatch, border_radius=2)
    pygame.draw.rect(surf, (100, 100, 100), swatch, 1, border_radius=2)
    draw_text(surf, label, swatch.right + 6, rect.centery, font, anchor="midleft")


# ---------------------------------------------------------------------------
# Painel esquerdo — Paleta de texturas
# ---------------------------------------------------------------------------

# tamanho de cada célula da paleta
PALETTE_CELL = 52
PALETTE_COLS = 3   # quantas colunas de brushes por categoria

def draw_left_panel(surf, state: EditorState, tex_mgr: TextureManager,
                    left_rect: pygame.Rect, fonts, mouse_pos, clicked) -> dict:
    """
    Painel esquerdo estilo paleta do Photoshop.

    Layout:
      - Abas de categoria (wall / floor / door / box)
      - Grade de brushes da categoria ativa
      - Botão "+" para importar novo brush
      - Botão "-" para remover brush selecionado
      - Toggle textura ON/OFF
    """
    actions = {}
    surf.fill(COL_LEFT, left_rect)
    pygame.draw.line(surf, (60, 60, 70),
                     left_rect.topright, left_rect.bottomright, 1)

    fn  = fonts["normal"]
    fb  = fonts["bold"]
    fsm = fonts["small"]
    mx, my = mouse_pos
    x0  = left_rect.x + 8
    pw  = left_rect.width - 16
    y   = left_rect.y + 8

    draw_text(surf, "TEXTURAS", x0, y, fb, COL_ACCENT)
    y += 22

    # ---- abas de categoria -------------------------------------------------
    cat_labels = [("wall", "Parede"), ("floor", "Chão"),
                  ("door", "Porta"),  ("box",   "Caixa")]
    tab_w = pw // len(cat_labels)
    for i, (cat, label) in enumerate(cat_labels):
        r = pygame.Rect(x0 + i * tab_w, y, tab_w - 2, 24)
        is_act = state.palette_cat == cat
        hov    = r.collidepoint(mx, my)
        bg = COL_BTN_ACT if is_act else (COL_BTN_HOV if hov else COL_BTN)
        pygame.draw.rect(surf, bg, r, border_radius=4)
        pygame.draw.rect(surf, (70, 70, 80), r, 1, border_radius=4)
        draw_text(surf, label, r.centerx, r.centery, fsm, anchor="center")
        if hov and clicked:
            actions["palette_cat"] = cat
    y += 30

    # ---- grade de brushes --------------------------------------------------
    cat      = state.palette_cat
    brushes  = tex_mgr.brushes_of(cat)
    act_idx  = tex_mgr.active.get(cat, -1)

    cell_sz  = PALETTE_CELL
    cols     = max(1, pw // (cell_sz + 4))
    pad      = (pw - cols * cell_sz) // max(1, cols + 1)

    # área de rolagem — apenas pintamos o que cabe
    palette_area_top = y
    palette_area_h   = left_rect.bottom - y - 80   # reserva espaço para botões
    palette_clip     = pygame.Rect(left_rect.x, palette_area_top,
                                   left_rect.width, palette_area_h)

    old_clip = surf.get_clip()
    surf.set_clip(palette_clip)

    for i, (global_idx, brush) in enumerate(brushes):
        col_i = i % cols
        row_i = i // cols
        bx = x0 + col_i * (cell_sz + pad) + pad // 2
        by = palette_area_top + row_i * (cell_sz + 6) + 3

        if by + cell_sz > palette_area_top + palette_area_h:
            break   # sem rolagem por enquanto; brushes extras ficam ocultos

        cell_r = pygame.Rect(bx, by, cell_sz, cell_sz)
        prev   = brush.preview(cell_sz)
        is_sel = (global_idx == act_idx)
        hov_b  = cell_r.collidepoint(mx, my)

        if prev:
            surf.blit(prev, cell_r)
        else:
            pygame.draw.rect(surf, (50, 50, 60), cell_r)
            draw_text(surf, "?", cell_r.centerx, cell_r.centery, fn,
                      COL_TEXT_DIM, anchor="center")

        # borda: amarela = selecionado, azul = hover, cinza = normal
        border_col = (255, 220, 60) if is_sel else (COL_ACCENT if hov_b else (70, 70, 85))
        border_w   = 2 if (is_sel or hov_b) else 1
        pygame.draw.rect(surf, border_col, cell_r, border_w)

        # código do brush (apenas para a categoria wall)
        if cat == "wall":
            wall_brushes_so_far = sum(
                1 for ii, bb in enumerate(tex_mgr.brushes)
                if bb.category == "wall" and ii < global_idx
            )
            code_lbl = cell_to_wall_code(brush_registry_to_cell(wall_brushes_so_far))
            code_surf = fsm.render(code_lbl, True, (255, 220, 60) if is_sel else (180, 180, 200))
            # fundo escuro semi-transparente
            bg_r = code_surf.get_rect(bottomright=(cell_r.right - 2, cell_r.bottom - 2))
            bg_s = pygame.Surface((bg_r.width + 4, bg_r.height + 2), pygame.SRCALPHA)
            bg_s.fill((0, 0, 0, 160))
            surf.blit(bg_s, (bg_r.x - 2, bg_r.y - 1))
            surf.blit(code_surf, bg_r)

        if hov_b and clicked:
            actions["select_brush"] = global_idx

    surf.set_clip(old_clip)

    # ---- botões importar / remover -----------------------------------------
    btn_y = left_rect.bottom - 74
    pygame.draw.line(surf, (55, 55, 65), (x0, btn_y), (x0 + pw, btn_y), 1)
    btn_y += 6

    btn_half = (pw - 4) // 2
    r_imp = pygame.Rect(x0, btn_y, btn_half, 24)
    r_rem = pygame.Rect(x0 + btn_half + 4, btn_y, btn_half, 24)
    hov_i = r_imp.collidepoint(mx, my)
    hov_r = r_rem.collidepoint(mx, my)
    draw_button(surf, r_imp, "+ Importar", fsm, hover=hov_i, active=True)
    draw_button(surf, r_rem, "- Remover",  fsm, hover=hov_r, danger=True)
    if hov_i and clicked:
        actions["import_brush"] = cat
    if hov_r and clicked:
        actions["remove_brush"] = act_idx

    # ---- exportar brush ativo ----------------------------------------------
    btn_y += 30
    r_exp = pygame.Rect(x0, btn_y, pw, 22)
    hov_e = r_exp.collidepoint(mx, my)
    draw_button(surf, r_exp, "Exportar brush ativo", fsm, hover=hov_e)
    if hov_e and clicked:
        actions["export_brush"] = cat

    # ---- toggle textura na grade -------------------------------------------
    btn_y += 28
    r_tex = pygame.Rect(x0, btn_y, pw, 24)
    hov_t = r_tex.collidepoint(mx, my)
    using_tex = state.show_texture
    draw_button(surf, r_tex,
                "Textura  ON" if using_tex else "Textura  OFF",
                fn, hover=hov_t, active=using_tex)
    if hov_t and clicked:
        actions["toggle_texture"] = True

    return actions


# ---------------------------------------------------------------------------
# Desenho da grade
# ---------------------------------------------------------------------------

def draw_grid(surf, state: EditorState, tex_mgr: TextureManager,
              canvas_rect: pygame.Rect, mouse_gxy,
              shape_cells: list[tuple[int, int]]):
    data  = state.current()
    rows  = state.rows()
    cols  = state.cols()
    cs    = state.cell_px
    gr    = state.grid_rect(canvas_rect)
    use_tex = state.show_texture

    surf.fill(COL_BG, canvas_rect)

    col0 = max(0, (canvas_rect.x - gr.x) // cs)
    row0 = max(0, (canvas_rect.y - gr.y) // cs)
    col1 = min(cols, col0 + canvas_rect.width  // cs + 2)
    row1 = min(rows, row0 + canvas_rect.height // cs + 2)

    shape_set = set(shape_cells)

    for gy in range(row0, row1):
        for gx in range(col0, col1):
            val  = data[gy][gx]
            rx   = gr.x + gx * cs
            ry   = gr.y + gy * cs
            cell = pygame.Rect(rx, ry, cs, cs)
            hover = (gx, gy) == mouse_gxy
            in_shape = (gx, gy) in shape_set

            if in_shape:
                pygame.draw.rect(surf, (100, 180, 255), cell)
            elif use_tex and cs >= 10:
                if val == 3:
                    prev = tex_mgr.get_cell_preview("door", cs)
                elif val == 0:
                    prev = tex_mgr.get_cell_preview("floor", cs)
                elif is_wall_cell(val):
                    prev = tex_mgr.preview_for_cell(val, cs)
                else:
                    prev = None

                if prev:
                    surf.blit(prev, cell)
                    if hover:
                        ov = pygame.Surface((cs, cs), pygame.SRCALPHA)
                        ov.fill((255, 255, 255, 50))
                        surf.blit(ov, cell)
                    # sobrepõe código da textura para paredes não-padrão
                    if is_wall_cell(val) and val >= 10000 and cs >= 16:
                        code_lbl = cell_to_wall_code(val)
                        fnt_code = pygame.font.SysFont(None, max(11, cs // 2))
                        cs_surf  = fnt_code.render(code_lbl, True, (255, 240, 100))
                        cs_rect  = cs_surf.get_rect(bottomright=(cell.right - 1, cell.bottom - 1))
                        bg_s = pygame.Surface((cs_surf.get_width() + 3, cs_surf.get_height() + 2), pygame.SRCALPHA)
                        bg_s.fill((0, 0, 0, 160))
                        surf.blit(bg_s, (cs_rect.x - 1, cs_rect.y - 1))
                        surf.blit(cs_surf, cs_rect)
                else:
                    _draw_cell_color(surf, cell, val, hover)
            else:
                _draw_cell_color(surf, cell, val, hover)

            if state.sel_door == (state.active, gx, gy):
                pygame.draw.rect(surf, (255, 220, 60), cell, 2)
            elif hover:
                pygame.draw.rect(surf, COL_GRID_HI, cell, 1)
            else:
                pygame.draw.rect(surf, COL_GRID, cell, 1)

            if val == 3 and cs >= 16:
                fnt_ico = pygame.font.SysFont(None, max(12, cs - 4))
                linked  = (state.active, gx, gy) in state.tp
                ico = fnt_ico.render("→" if linked else "?",
                                     True,
                                     (255, 240, 100) if linked else (255, 160, 80))
                surf.blit(ico, ico.get_rect(center=cell.center))

    for i, b in enumerate(state.current_boxes()):
        _draw_box_on_grid(surf, state, tex_mgr, gr, cs, b, i, mouse_gxy)

    pygame.draw.rect(surf, (70, 70, 80), gr, 1)


def _draw_cell_color(surf, cell, val, hover):
    if is_wall_cell(val):
        col = COL_WALL_LIT if hover else COL_WALL
    elif val == 3:
        col = COL_DOOR_LIT if hover else COL_DOOR
    else:
        col = (35, 35, 40) if hover else COL_EMPTY
    pygame.draw.rect(surf, col, cell)


def _draw_box_on_grid(surf, state, tex_mgr, gr, cs, b: "BoxObj", idx: int, mouse_gxy):
    px = gr.x + b.x * cs
    py = gr.y + b.y * cs
    half = b.size * cs / 2
    sel  = state.sel_box == idx

    if b.shape == "circle":
        cx, cy = int(px), int(py)
        r_px   = int(half)
        prev = tex_mgr.get_preview("box", r_px * 2) if r_px > 4 else None
        if prev:
            clip_surf = pygame.Surface((r_px * 2, r_px * 2), pygame.SRCALPHA)
            pygame.draw.circle(clip_surf, (255, 255, 255), (r_px, r_px), r_px)
            clip_surf.blit(prev, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(clip_surf, (cx - r_px, cy - r_px))
        else:
            pygame.draw.circle(surf, COL_BOX_FILL, (cx, cy), max(3, int(half)))
        pygame.draw.circle(surf, (255, 220, 60) if sel else (180, 140, 40),
                           (cx, cy), max(3, int(half)), 2)
    else:
        rect = pygame.Rect(int(px - half), int(py - half),
                           max(4, int(half * 2)), max(4, int(half * 2)))
        prev = tex_mgr.get_preview("box", max(4, int(half * 2))) if half > 4 else None
        if prev:
            surf.blit(prev, rect)
        else:
            pygame.draw.rect(surf, COL_BOX_FILL, rect)
        pygame.draw.rect(surf, (255, 220, 60) if sel else (180, 140, 40), rect, 2)

    if cs >= 16:
        fnt = pygame.font.SysFont(None, max(12, cs // 2))
        lbl = fnt.render(str(idx), True, (255, 255, 200))
        surf.blit(lbl, lbl.get_rect(center=(int(px), int(py))))


# ---------------------------------------------------------------------------
# Painel direito
# ---------------------------------------------------------------------------

def draw_panel(surf, state: EditorState, panel_rect: pygame.Rect,
               fonts, mouse_pos, clicked) -> dict:
    actions = {}
    surf.fill(COL_PANEL, panel_rect)
    pygame.draw.line(surf, (60, 60, 70),
                     panel_rect.topleft, panel_rect.bottomleft, 1)

    fn  = fonts["normal"]
    fb  = fonts["bold"]
    fsm = fonts["small"]
    mx, my = mouse_pos
    x0  = panel_rect.x + 10
    y   = panel_rect.y + 10
    pw  = panel_rect.width - 20

    draw_text(surf, "FERRAMENTA", x0, y, fb, COL_TEXT_DIM)
    y += 22

    tools = [
        (TOOL_FLOOR,  "Chão",      COL_EMPTY,    "1"),
        (TOOL_WALL,   "Parede",    COL_WALL,     "2"),
        (TOOL_DOOR,   "Porta",     COL_DOOR,     "3"),
        (TOOL_BOX,    "Caixa",     COL_BOX_FILL, "4"),
        (TOOL_RECT,   "Retângulo", (100,100,200),"5"),
        (TOOL_CIRCLE, "Círculo",   (180,100,200),"6"),
    ]
    for tid, tlabel, tcol, tkey in tools:
        r = pygame.Rect(x0, y, pw, 26)
        hov = r.collidepoint(mx, my)
        draw_tool_btn(surf, r, f"{tlabel}  [{tkey}]", tcol, fn,
                      active=(state.tool == tid), hover=hov)
        if hov and clicked:
            actions["tool"] = tid
        y += 30

    y += 6
    pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
    y += 8

    if state.tool in (TOOL_RECT, TOOL_CIRCLE):
        draw_text(surf, "PREENCHER COM", x0, y, fb, COL_TEXT_DIM)
        y += 20
        fill_opts = [(1, "Parede", COL_WALL), (0, "Chão", COL_EMPTY), (3, "Porta", COL_DOOR)]
        for fv, fl, fc in fill_opts:
            r = pygame.Rect(x0, y, pw, 24)
            hov = r.collidepoint(mx, my)
            draw_tool_btn(surf, r, fl, fc, fsm,
                          active=(state.fill_val == fv), hover=hov)
            if hov and clicked:
                actions["fill_val"] = fv
            y += 28
        y += 4
        pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
        y += 8

    if state.tool == TOOL_BOX:
        draw_text(surf, "NOVA CAIXA", x0, y, fb, COL_TEXT_DIM)
        y += 20

        draw_text(surf, f"Tamanho: {state.new_box_size:.2f}", x0, y, fn)
        y += 20
        for i, (lbl, dv) in enumerate([("−", -0.05), ("+", 0.05)]):
            r = pygame.Rect(x0 + i * (pw // 2 + 2), y, pw // 2 - 2, 22)
            hov = r.collidepoint(mx, my)
            draw_button(surf, r, lbl, fn, hover=hov)
            if hov and clicked:
                actions["box_size"] = dv
        y += 28

        draw_text(surf, "Forma:", x0, y, fn)
        y += 20
        for shp, lbl in [("square", "Quadrado"), ("circle", "Círculo")]:
            r = pygame.Rect(x0, y, pw, 22)
            hov = r.collidepoint(mx, my)
            draw_button(surf, r, lbl, fn, hover=hov,
                        active=(state.new_box_shape == shp))
            if hov and clicked:
                actions["box_shape"] = shp
            y += 26

        y += 4
        pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
        y += 8

    blist = state.current_boxes()
    if state.sel_box is not None and 0 <= state.sel_box < len(blist):
        b = blist[state.sel_box]
        draw_text(surf, f"CAIXA #{state.sel_box}", x0, y, fb, COL_TEXT_DIM)
        y += 20
        draw_text(surf, f"pos: ({b.x:.2f}, {b.y:.2f})", x0, y, fsm, COL_TEXT)
        y += 18
        draw_text(surf, f"size: {b.size:.2f}  shape: {b.shape}", x0, y, fsm, COL_TEXT)
        y += 20

        for i, (lbl, dv) in enumerate([("size−", -0.05), ("size+", 0.05)]):
            r = pygame.Rect(x0 + i * (pw // 2 + 2), y, pw // 2 - 2, 22)
            hov = r.collidepoint(mx, my)
            draw_button(surf, r, lbl, fsm, hover=hov)
            if hov and clicked:
                actions["sel_box_size"] = dv
        y += 28

        for shp, lbl in [("square", "Quadrado"), ("circle", "Círculo")]:
            r = pygame.Rect(x0, y, pw, 22)
            hov = r.collidepoint(mx, my)
            draw_button(surf, r, lbl, fn, hover=hov,
                        active=(b.shape == shp))
            if hov and clicked:
                actions["sel_box_shape"] = shp
            y += 26

        r_del = pygame.Rect(x0, y, pw, 24)
        hov_d = r_del.collidepoint(mx, my)
        draw_button(surf, r_del, "Remover caixa", fn, hover=hov_d, danger=True)
        if hov_d and clicked:
            actions["del_box"] = True
        y += 30

        y += 4
        pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
        y += 8

    if state.tool == TOOL_DOOR or state.sel_door:
        draw_text(surf, "PORTA SELECIONADA", x0, y, fb, COL_TEXT_DIM)
        y += 20

        if state.sel_door and state.sel_door[0] == state.active:
            smid, sgx, sgy = state.sel_door
            draw_text(surf, f"({sgx}, {sgy})  mapa {smid}", x0, y, fn)
            y += 20
            dest = state.tp.get((smid, sgx, sgy))
            if dest:
                dmid, dgx, dgy = dest
                draw_text(surf, f"→ {dmid} ({dgx},{dgy})", x0, y, fn, COL_ACCENT)
            else:
                draw_text(surf, "Sem destino", x0, y, fn, COL_TEXT_DIM)
            y += 20

            draw_text(surf, "Ligar a:", x0, y, fsm, COL_TEXT_DIM)
            y += 16

            for oid, odata in state.maps.items():
                oh = len(odata)
                ow = len(odata[0]) if odata else 0
                for ogy in range(oh):
                    for ogx in range(ow):
                        if odata[ogy][ogx] == 3 and (oid, ogx, ogy) != state.sel_door:
                            is_cur = dest == (oid, ogx, ogy)
                            r = pygame.Rect(x0, y, pw, 24)
                            hov = r.collidepoint(mx, my)
                            col_bg = COL_BTN_ACT if is_cur else (COL_BTN_HOV if hov else COL_BTN)
                            pygame.draw.rect(surf, col_bg, r, border_radius=4)
                            pygame.draw.rect(surf, (70, 70, 80), r, 1, border_radius=4)
                            draw_text(surf, f"  {oid} ({ogx},{ogy})",
                                      r.x + 6, r.centery, fn, anchor="midleft")
                            if hov and clicked:
                                actions["link_door"] = (oid, ogx, ogy)
                            y += 28
                            if y > panel_rect.bottom - 100:
                                break
                    if y > panel_rect.bottom - 100:
                        break

            if dest:
                r = pygame.Rect(x0, y, pw, 24)
                hov = r.collidepoint(mx, my)
                draw_button(surf, r, "Desvincular", fn, hover=hov, danger=True)
                if hov and clicked:
                    actions["unlink_door"] = True
                y += 30
        else:
            draw_text(surf, "Clique numa porta (3)", x0, y, fn, COL_TEXT_DIM)
            y += 20

        y += 4
        pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
        y += 8

    draw_text(surf, "TAMANHO DA GRADE", x0, y, fb, COL_TEXT_DIM)
    y += 20
    rows, cols = state.rows(), state.cols()
    draw_text(surf, f"{cols} × {rows} células", x0, y, fn)
    y += 22

    btn_sz = (pw - 6) // 4
    for i, (act, lbl) in enumerate([("-col","−C"),("+col","+C"),("-row","−R"),("+row","+R")]):
        r = pygame.Rect(x0 + i * (btn_sz + 2), y, btn_sz, 24)
        hov = r.collidepoint(mx, my)
        draw_button(surf, r, lbl, fsm, hover=hov)
        if hov and clicked:
            actions["resize"] = act
    y += 32

    y += 4
    draw_text(surf, f"ZOOM  {state.cell_px}px", x0, y, fb, COL_TEXT_DIM)
    y += 20
    for i, (lbl, dz) in enumerate([("−", -2), ("+", 2)]):
        r = pygame.Rect(x0 + i * (pw // 2 + 2), y, pw // 2 - 2, 24)
        hov = r.collidepoint(mx, my)
        draw_button(surf, r, lbl, fn, hover=hov)
        if hov and clicked:
            actions["zoom"] = dz
    y += 32

    y = panel_rect.bottom - 70
    pygame.draw.line(surf, (60, 60, 70), (x0, y), (x0 + pw, y), 1)
    y += 8

    r_undo = pygame.Rect(x0, y, pw // 2 - 4, 28)
    r_save = pygame.Rect(x0 + pw // 2 + 4, y, pw // 2 - 4, 28)
    hov_u  = r_undo.collidepoint(mx, my)
    hov_s  = r_save.collidepoint(mx, my)
    draw_button(surf, r_undo, "Desfazer  Z", fn, hover=hov_u)
    draw_button(surf, r_save, "Salvar  S", fn, hover=hov_s, active=True)
    if hov_u and clicked: actions["undo"] = True
    if hov_s and clicked: actions["save"] = True

    return actions


# ---------------------------------------------------------------------------
# Barra de abas
# ---------------------------------------------------------------------------

def draw_tabbar(surf, state: EditorState, tabbar_rect: pygame.Rect,
                fonts, mouse_pos, clicked) -> dict:
    actions = {}
    surf.fill(COL_TABBAR, tabbar_rect)
    pygame.draw.line(surf, (55, 55, 65),
                     tabbar_rect.bottomleft, tabbar_rect.bottomright, 1)

    fn  = fonts["normal"]
    fsm = fonts["small"]
    mx, my = mouse_pos
    x   = tabbar_rect.x + LEFT_W + 6
    TAB_H   = tabbar_rect.height - 6
    TAB_PAD = 10
    CLO_W   = 16

    for mid in state.map_ids:
        tw = fn.size(mid)[0] + TAB_PAD * 2 + CLO_W + 4
        r  = pygame.Rect(x, tabbar_rect.y + 3, tw, TAB_H)
        is_act = (mid == state.active)
        hov    = r.collidepoint(mx, my)
        bg     = COL_TAB_ACT if is_act else (COL_TAB_HOV if hov else COL_TABBAR)
        pygame.draw.rect(surf, bg, r, border_radius=5)
        if is_act:
            pygame.draw.rect(surf, COL_ACCENT, r, 1, border_radius=5)

        if state.renaming == mid:
            draw_text(surf, state.rename_buf + "|", r.x + TAB_PAD, r.centery,
                      fn, anchor="midleft")
        else:
            draw_text(surf, mid, r.x + TAB_PAD, r.centery, fn, anchor="midleft")

        cx_r = pygame.Rect(r.right - CLO_W - 2, r.centery - 7, 14, 14)
        hov_c = cx_r.collidepoint(mx, my)
        if hov_c:
            pygame.draw.rect(surf, COL_DANGER, cx_r, border_radius=3)
        draw_text(surf, "×", cx_r.centerx, cx_r.centery, fsm,
                  color=(255, 255, 255) if hov_c else COL_TEXT_DIM, anchor="center")

        if hov and clicked and not cx_r.collidepoint(mx, my):
            if is_act:
                actions["rename_start"] = mid
            else:
                actions["switch_tab"] = mid
        if hov_c and clicked:
            actions["delete_tab"] = mid

        x += tw + 4

    add_r = pygame.Rect(x, tabbar_rect.y + 3, 28, TAB_H)
    hov_a = add_r.collidepoint(mx, my)
    draw_button(surf, add_r, "+", fn, hover=hov_a)
    if hov_a and clicked:
        actions["new_tab"] = True

    return actions


# ---------------------------------------------------------------------------
# Barra de ferramentas superior
# ---------------------------------------------------------------------------

def draw_toolbar(surf, state: EditorState, toolbar_rect: pygame.Rect,
                 fonts, mouse_pos, clicked) -> dict:
    actions = {}
    surf.fill(COL_TOOLBAR, toolbar_rect)
    pygame.draw.line(surf, (55, 55, 65),
                     toolbar_rect.bottomleft, toolbar_rect.bottomright, 1)

    fn = fonts["normal"]
    fb = fonts["bold"]
    mx, my = mouse_pos

    draw_text(surf, "MAP EDITOR", toolbar_rect.x + 14, toolbar_rect.centery,
              fb, COL_ACCENT, anchor="midleft")

    tool_defs = [
        (TOOL_FLOOR,  "Chão[1]",     COL_EMPTY),
        (TOOL_WALL,   "Parede[2]",   COL_WALL),
        (TOOL_DOOR,   "Porta[3]",    COL_DOOR),
        (TOOL_BOX,    "Caixa[4]",    COL_BOX_FILL),
        (TOOL_RECT,   "Ret.[5]",     (100,100,200)),
        (TOOL_CIRCLE, "Circ.[6]",    (180,100,200)),
    ]
    tx = toolbar_rect.x + LEFT_W + 10
    for tid, tlabel, tcol in tool_defs:
        tw = fn.size(tlabel)[0] + 26
        r  = pygame.Rect(tx, toolbar_rect.centery - 13, tw, 26)
        hov = r.collidepoint(mx, my)
        draw_tool_btn(surf, r, tlabel, tcol, fn,
                      active=(state.tool == tid), hover=hov)
        if hov and clicked:
            actions["tool"] = tid
        tx += tw + 4

    r_s = pygame.Rect(toolbar_rect.right - PANEL_W - 10 - 90,
                      toolbar_rect.centery - 13, 88, 26)
    hov_s = r_s.collidepoint(mx, my)
    draw_button(surf, r_s, "Salvar  Ctrl+S", fn, hover=hov_s, active=True)
    if hov_s and clicked:
        actions["save"] = True

    return actions


# ---------------------------------------------------------------------------
# Diálogo de input simples (renomear mapa)
# ---------------------------------------------------------------------------

def draw_input_dialog(surf, prompt, buf, fonts):
    fn = fonts["normal"]
    fb = fonts["bold"]
    w, h = 340, 110
    sw, sh = surf.get_size()
    r = pygame.Rect((sw - w) // 2, (sh - h) // 2, w, h)
    pygame.draw.rect(surf, (42, 42, 48), r, border_radius=8)
    pygame.draw.rect(surf, COL_ACCENT, r, 2, border_radius=8)
    draw_text(surf, prompt, r.centerx, r.y + 18, fb, anchor="midtop")
    field = pygame.Rect(r.x + 16, r.y + 52, r.width - 32, 32)
    pygame.draw.rect(surf, (28, 28, 34), field, border_radius=5)
    pygame.draw.rect(surf, COL_ACCENT, field, 1, border_radius=5)
    draw_text(surf, buf + "|", field.x + 8, field.centery, fn, anchor="midleft")
    draw_text(surf, "Enter = confirmar    Esc = cancelar",
              r.centerx, r.bottom - 14, fonts["small"], COL_TEXT_DIM, anchor="midbottom")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Map Editor")
    clock  = pygame.time.Clock()

    fonts = {
        "normal": pygame.font.SysFont(None, 24),
        "bold":   pygame.font.SysFont(None, 24, bold=True),
        "small":  pygame.font.SysFont(None, 19),
    }

    state   = EditorState()
    tex_mgr = TextureManager()

    dialog        = None    # None | "new_map"
    dialog_buf    = ""
    save_flash    = 0
    panning       = False
    pan_origin    = (0, 0)
    pan_offset_orig = (0, 0)
    last_painted  = None
    dragging_box  = False
    drag_box_orig = (0.0, 0.0)
    drag_mouse_orig = (0, 0)

    while True:
        sw, sh = screen.get_size()

        toolbar_rect = pygame.Rect(0, 0, sw, TOOLBAR_H)
        tabbar_rect  = pygame.Rect(0, TOOLBAR_H, sw, TABBAR_H)
        left_rect    = pygame.Rect(0, TOOLBAR_H + TABBAR_H,
                                   LEFT_W, sh - TOOLBAR_H - TABBAR_H - STATUS_H)
        panel_rect   = pygame.Rect(sw - PANEL_W, TOOLBAR_H + TABBAR_H,
                                   PANEL_W, sh - TOOLBAR_H - TABBAR_H - STATUS_H)
        canvas_rect  = pygame.Rect(LEFT_W, TOOLBAR_H + TABBAR_H,
                                   sw - LEFT_W - PANEL_W,
                                   sh - TOOLBAR_H - TABBAR_H - STATUS_H)
        status_rect  = pygame.Rect(0, sh - STATUS_H, sw, STATUS_H)

        mx, my = pygame.mouse.get_pos()
        mouse_gxy = (-1, -1)
        gr = state.grid_rect(canvas_rect)
        if canvas_rect.collidepoint(mx, my) and gr.collidepoint(mx, my):
            mouse_gxy = state.screen_to_grid(mx, my, gr)

        clicked      = False
        scroll_delta = 0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if ev.type == pygame.KEYDOWN:
                if dialog == "new_map":
                    if ev.key == pygame.K_RETURN:
                        nid = dialog_buf.strip().upper() or "X"
                        state.snapshot()
                        state.add_map(nid)
                        dialog = None; dialog_buf = ""
                    elif ev.key == pygame.K_ESCAPE:
                        dialog = None; dialog_buf = ""
                    elif ev.key == pygame.K_BACKSPACE:
                        dialog_buf = dialog_buf[:-1]
                    else:
                        if len(dialog_buf) < 10 and ev.unicode.isprintable():
                            dialog_buf += ev.unicode.upper()
                    continue

                if state.renaming:
                    if ev.key == pygame.K_RETURN:
                        state.snapshot()
                        state.rename_map(state.renaming, state.rename_buf.strip().upper())
                        state.renaming = None; state.rename_buf = ""
                    elif ev.key == pygame.K_ESCAPE:
                        state.renaming = None; state.rename_buf = ""
                    elif ev.key == pygame.K_BACKSPACE:
                        state.rename_buf = state.rename_buf[:-1]
                    else:
                        if len(state.rename_buf) < 10 and ev.unicode.isprintable():
                            state.rename_buf += ev.unicode.upper()
                    continue

                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL:
                    if ev.key == pygame.K_s:
                        state.save(); save_flash = 90
                    if ev.key == pygame.K_z:
                        state.undo()
                else:
                    if ev.key == pygame.K_1: state.tool = TOOL_FLOOR
                    if ev.key == pygame.K_2: state.tool = TOOL_WALL
                    if ev.key == pygame.K_3: state.tool = TOOL_DOOR
                    if ev.key == pygame.K_4: state.tool = TOOL_BOX
                    if ev.key == pygame.K_5: state.tool = TOOL_RECT
                    if ev.key == pygame.K_6: state.tool = TOOL_CIRCLE
                    if ev.key == pygame.K_f: state.tool = TOOL_FLOOR
                    if ev.key == pygame.K_w: state.tool = TOOL_WALL
                    if ev.key == pygame.K_d: state.tool = TOOL_DOOR
                    if ev.key == pygame.K_z: state.undo()
                    if ev.key == pygame.K_DELETE and state.sel_box is not None:
                        state.snapshot(); state.remove_selected_box()

            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    clicked = True
                if ev.button == 2:
                    panning = True
                    pan_origin = ev.pos
                    pan_offset_orig = (state.offset[0], state.offset[1])
                if ev.button == 4: scroll_delta = +2
                if ev.button == 5: scroll_delta = -2

            if ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    if state.tool in (TOOL_RECT, TOOL_CIRCLE) and state.shape_start:
                        gx0, gy0 = state.shape_start
                        gx1, gy1 = mouse_gxy
                        state.snapshot()
                        state.apply_shape(gx0, gy0, gx1, gy1, tex_mgr)
                        state.shape_start   = None
                        state.shape_preview = []
                    state.painting  = False
                    last_painted    = None
                    dragging_box    = False
                if ev.button == 2:
                    panning = False

            if ev.type == pygame.MOUSEMOTION:
                if panning:
                    dx = ev.pos[0] - pan_origin[0]
                    dy = ev.pos[1] - pan_origin[1]
                    state.offset[0] = pan_offset_orig[0] + dx
                    state.offset[1] = pan_offset_orig[1] + dy
                if dragging_box and state.sel_box is not None:
                    blist = state.current_boxes()
                    if 0 <= state.sel_box < len(blist):
                        dmx = ev.pos[0] - drag_mouse_orig[0]
                        dmy = ev.pos[1] - drag_mouse_orig[1]
                        blist[state.sel_box].x = drag_box_orig[0] + dmx / state.cell_px
                        blist[state.sel_box].y = drag_box_orig[1] + dmy / state.cell_px

        # ---- zoom -----------------------------------------------------------
        if scroll_delta and canvas_rect.collidepoint(mx, my):
            old_cs = state.cell_px
            new_cs = max(CELL_MIN, min(CELL_MAX, state.cell_px + scroll_delta))
            if new_cs != old_cs:
                rel_x = mx - (canvas_rect.x + state.offset[0])
                rel_y = my - (canvas_rect.y + state.offset[1])
                state.offset[0] = int(mx - canvas_rect.x - rel_x * new_cs / old_cs)
                state.offset[1] = int(my - canvas_rect.y - rel_y * new_cs / old_cs)
                state.cell_px   = new_cs

        # ---- preview de shape -----------------------------------------------
        if state.tool in (TOOL_RECT, TOOL_CIRCLE) and state.shape_start:
            gx0, gy0 = state.shape_start
            gx1, gy1 = mouse_gxy
            if state.tool == TOOL_RECT:
                state.shape_preview = state.cells_rect(gx0, gy0, gx1, gy1)
            else:
                state.shape_preview = state.cells_circle(gx0, gy0, gx1, gy1)
        elif not (state.tool in (TOOL_RECT, TOOL_CIRCLE) and state.shape_start):
            state.shape_preview = []

        # ---- pintura / interação na grade -----------------------------------
        btn1, _, btn3 = pygame.mouse.get_pressed()

        if canvas_rect.collidepoint(mx, my) and not dialog:
            gx, gy = mouse_gxy
            in_grid = 0 <= gx < state.cols() and 0 <= gy < state.rows()

            if btn1 and clicked:
                if state.tool in (TOOL_RECT, TOOL_CIRCLE) and in_grid:
                    state.shape_start = (gx, gy)

                elif state.tool == TOOL_BOX and in_grid:
                    bi = state.box_at(gx, gy)
                    if bi is not None:
                        state.sel_box = bi
                        dragging_box  = True
                        b = state.current_boxes()[bi]
                        drag_box_orig   = (b.x, b.y)
                        drag_mouse_orig = (mx, my)
                        state.snapshot()
                    else:
                        state.snapshot()
                        state.add_box(gx, gy)

                elif in_grid and state.tool not in (TOOL_RECT, TOOL_CIRCLE, TOOL_BOX):
                    cur_val = state.current()[gy][gx]
                    if not state.painting and cur_val == 3 and state.tool == TOOL_DOOR:
                        state.sel_door = (state.active, gx, gy)
                        last_painted   = (gx, gy)
                    else:
                        if not state.painting:
                            state.snapshot()
                            state.painting = True
                        state.set_cell(gx, gy, state._cell_value(tex_mgr))
                        last_painted = (gx, gy)
                        if state.tool == TOOL_DOOR:
                            state.sel_door = (state.active, gx, gy)

            elif btn1 and not clicked and in_grid:
                if state.tool not in (TOOL_RECT, TOOL_CIRCLE, TOOL_BOX):
                    if (gx, gy) != last_painted:
                        if not state.painting:
                            state.snapshot()
                            state.painting = True
                        state.set_cell(gx, gy, state._cell_value(tex_mgr))
                        last_painted = (gx, gy)

            if btn3 and in_grid and (gx, gy) != last_painted:
                if not state.painting:
                    state.snapshot()
                    state.painting = True
                state.set_cell(gx, gy, 0)
                last_painted = (gx, gy)

        # ---- desenho --------------------------------------------------------
        tb_actions = draw_toolbar(screen, state, toolbar_rect, fonts, (mx, my), clicked)
        if "tool" in tb_actions: state.tool = tb_actions["tool"]
        if "save" in tb_actions: state.save(); save_flash = 90

        tab_actions = draw_tabbar(screen, state, tabbar_rect, fonts, (mx, my), clicked)
        if "switch_tab"   in tab_actions: state.active = tab_actions["switch_tab"]
        if "new_tab"      in tab_actions: dialog = "new_map"; dialog_buf = ""
        if "delete_tab"   in tab_actions:
            state.snapshot(); state.delete_map(tab_actions["delete_tab"])
        if "rename_start" in tab_actions:
            state.renaming   = tab_actions["rename_start"]
            state.rename_buf = state.renaming

        draw_grid(screen, state, tex_mgr, canvas_rect, mouse_gxy, state.shape_preview)

        left_actions = draw_left_panel(screen, state, tex_mgr, left_rect,
                                       fonts, (mx, my), clicked)

        if "palette_cat" in left_actions:
            state.palette_cat = left_actions["palette_cat"]

        if "select_brush" in left_actions:
            tex_mgr.set_active(left_actions["select_brush"])

        if "import_brush" in left_actions:
            cat = left_actions["import_brush"]
            # pausa pygame para o diálogo de arquivo não conflitar
            pygame.event.pump()
            path = open_file_dialog(
                title=f"Importar textura — {cat}",
                filetypes=[("Imagens PNG", "*.png"), ("Todos os arquivos", "*.*")],
            )
            if path and os.path.isfile(path):
                tex_mgr.import_brush(path, cat)

        if "remove_brush" in left_actions:
            idx = left_actions["remove_brush"]
            if idx >= 0:
                tex_mgr.remove_brush(idx)

        if "export_brush" in left_actions:
            cat = left_actions["export_brush"]
            src = tex_mgr.active_path(cat)
            if src and os.path.isfile(src):
                pygame.event.pump()
                dest = save_file_dialog(
                    title=f"Exportar textura — {cat}",
                    filetypes=[("Imagens PNG", "*.png"), ("Todos os arquivos", "*.*")],
                    initialfile=os.path.basename(src),
                )
                if dest:
                    shutil.copy2(src, dest)

        if "toggle_texture" in left_actions:
            state.show_texture = not state.show_texture

        p_actions = draw_panel(screen, state, panel_rect, fonts, (mx, my), clicked)
        if "tool"        in p_actions: state.tool = p_actions["tool"]
        if "fill_val"    in p_actions: state.fill_val = p_actions["fill_val"]
        if "undo"        in p_actions: state.undo()
        if "save"        in p_actions: state.save(); save_flash = 90
        if "zoom"        in p_actions:
            state.cell_px = max(CELL_MIN, min(CELL_MAX, state.cell_px + p_actions["zoom"]))
        if "box_size"    in p_actions:
            state.new_box_size = round(
                max(0.1, min(2.0, state.new_box_size + p_actions["box_size"])), 2)
        if "box_shape"   in p_actions:
            state.new_box_shape = p_actions["box_shape"]
        if "sel_box_size" in p_actions and state.sel_box is not None:
            blist = state.current_boxes()
            if 0 <= state.sel_box < len(blist):
                blist[state.sel_box].size = round(
                    max(0.1, min(2.0, blist[state.sel_box].size + p_actions["sel_box_size"])), 2)
        if "sel_box_shape" in p_actions and state.sel_box is not None:
            blist = state.current_boxes()
            if 0 <= state.sel_box < len(blist):
                blist[state.sel_box].shape = p_actions["sel_box_shape"]
        if "del_box"     in p_actions:
            state.snapshot(); state.remove_selected_box()
        if "resize"      in p_actions:
            act = p_actions["resize"]
            state.snapshot()
            data = state.current()
            rows, cols = state.rows(), state.cols()
            if   act == "+col": [row.append(0) for row in data]
            elif act == "-col" and cols > 2: [row.pop() for row in data]
            elif act == "+row": data.append([0] * cols)
            elif act == "-row" and rows > 2: data.pop()
        if "link_door"   in p_actions and state.sel_door:
            state.snapshot()
            dmid, dgx, dgy = p_actions["link_door"]
            smid, sgx, sgy = state.sel_door
            state.tp[(smid, sgx, sgy)] = (dmid, dgx, dgy)
            state.tp[(dmid, dgx, dgy)] = (smid, sgx, sgy)
        if "unlink_door" in p_actions and state.sel_door:
            state.snapshot()
            smid, sgx, sgy = state.sel_door
            dest = state.tp.pop((smid, sgx, sgy), None)
            if dest:
                state.tp.pop((dest[0], dest[1], dest[2]), None)

        # ---- status bar -----------------------------------------------------
        screen.fill(COL_STATUS_BG, status_rect)
        pygame.draw.line(screen, (55, 55, 65),
                         status_rect.topleft, status_rect.topright, 1)
        gx, gy = mouse_gxy
        # tooltip de brush sob o cursor no painel esquerdo
        brush_tip = ""
        if left_rect.collidepoint(mx, my):
            cat = state.palette_cat
            for global_idx, brush in tex_mgr.brushes_of(cat):
                if tex_mgr.active.get(cat) == global_idx:
                    brush_tip = f"  |  brush ativo: {os.path.basename(brush.path)}"
                    break

        if 0 <= gx < state.cols() and 0 <= gy < state.rows():
            val   = state.current()[gy][gx]
            vname = {0: "chão", 1: "parede", 3: "porta"}
            bi    = state.box_at(gx, gy)
            box_s = f"  | caixa #{bi}" if bi is not None else ""
            status = (f"célula ({gx},{gy})={val}({vname.get(val,'?')}){box_s}  "
                      f"|  mapa:{state.active} {state.cols()}×{state.rows()}  "
                      f"|  zoom:{state.cell_px}px{brush_tip}  "
                      f"|  scroll=zoom  meio=pan  ctrl+s=salvar  del=remover caixa")
        else:
            status = (f"mapa:{state.active} {state.cols()}×{state.rows()}  "
                      f"|  scroll=zoom  meio=pan  ctrl+s=salvar{brush_tip}")
        draw_text(screen, status, status_rect.x + 8, status_rect.centery,
                  fonts["small"], COL_TEXT_DIM, anchor="midleft")

        if save_flash > 0:
            save_flash -= 1
            draw_text(screen, "✓ Salvo!", status_rect.right - 90, status_rect.centery,
                      fonts["bold"], (80, 220, 100), anchor="midright")

        # ---- cursor de shape em andamento -----------------------------------
        if state.tool in (TOOL_RECT, TOOL_CIRCLE) and state.shape_start:
            gx0, gy0 = state.shape_start
            px0 = gr.x + gx0 * state.cell_px
            py0 = gr.y + gy0 * state.cell_px
            px1 = gr.x + (mouse_gxy[0] + 1) * state.cell_px
            py1 = gr.y + (mouse_gxy[1] + 1) * state.cell_px
            rr  = pygame.Rect(min(px0, px1 - state.cell_px),
                              min(py0, py1 - state.cell_px),
                              abs(px1 - px0), abs(py1 - py0))
            pygame.draw.rect(screen, (100, 180, 255), rr, 2)

        if dialog == "new_map":
            draw_input_dialog(screen, "Nome do novo mapa:", dialog_buf, fonts)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
