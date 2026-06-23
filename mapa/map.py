# Valores de célula:
#   0     = chão
#   1     = parede (textura padrão)
#   3     = teleporte (spawna o jogador no destino configurado)
#   '1A'  = parede com textura brush 1A  (num=1, letra=A)
#   '14B' = parede com textura brush 14B (num=14, letra=B)

_DATA_A = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    ['2A', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    ['2A', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '1A'],
    ['2A', 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 3, 0, '1A'],
    ['2A', 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, '1A'],
    ['2A', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
    ['2A', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    ['2A', 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1],
    ['2A', '2A', '2A', '2A', '2A', '2A', 1, 3, 1, 0, 0, 0, 0, 0, 0, 1],
    ['2A', 0, 0, 0, 0, '2A', 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    ['2A', 0, 0, 0, 0, '2A', 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    ['2A', 0, 0, '2A', 0, '2A', 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    ['2A', 0, 0, '2A', '2A', '2A', 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    ['2A', 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1],
    ['2A', 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    ['2A', 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

_DATA_B = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    [1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 1, 3, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 3, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 3, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

_DATA_C = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

_BOXES_A = [{'x': 10.5, 'y': 12.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 3.5, 'y': 7.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 7.5, 'y': 1.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 4.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 9.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 8.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 7.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 6.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}, {'x': 10.5, 'y': 5.5, 'size': 0.5, 'shape': 'circle', 'tex_index': 0}, {'x': 7.5, 'y': 5.5, 'size': 0.5, 'shape': 'square', 'tex_index': 0}]

_BOXES_B = []

_BOXES_C = []

# Tabela de teleportes:
#   chave  = (map_id, grid_x, grid_y)
#   valor  = (dest_map_id, dest_tp_gx, dest_tp_gy)
# O spawn exato é calculado em runtime.
TELEPORT_TABLE = {
    ("A",  7,  8): ("B",  7, 14),
    ("A", 13,  3): ("B",  1, 14),
    ("A",  1, 14): ("B", 14, 14),
    ("B",  1, 14): ("A",  7,  8),
    ("B",  7, 14): ("A", 13,  3),
    ("B", 14, 14): ("A",  1, 14),
    ("B",  8,  5): ("C",  2, 14),
    ("C",  2, 14): ("B",  8,  5),
}

def _cell_to_int(v) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s and s[-1].isalpha() and s[:-1].isdigit():
        num       = int(s[:-1])
        letra_idx = ord(s[-1].upper()) - ord('A')
        return 10000 + letra_idx * 100 + num
    return int(v)

class Map:
    def __init__(self, map_id: str = "A"):
        import sys
        _g = sys.modules[__name__].__dict__
        self.map_id = map_id
        raw         = _g.get(f"_DATA_{map_id}", _DATA_A if map_id == "A" else _DATA_B)
        self._data  = [[_cell_to_int(v) for v in row] for row in raw]
        self.width  = len(self._data[0])
        self.height = len(self._data)
        self.boxes  = _g.get(f"_BOXES_{map_id}", [])

    def get(self, x: int, y: int) -> int:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return 1
        return self._data[y][x]

    def near_teleport(self, px: float, py: float, radius: float = 1.2):
        """Retorna (dest_map_id, dest_tp_gx, dest_tp_gy) se houver célula 3 dentro de `radius` tiles, senão None."""
        import math
        ix, iy = int(px), int(py)
        r = int(math.ceil(radius))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                gx, gy = ix + dx, iy + dy
                if self.get(gx, gy) == 3:
                    cx, cy = gx + 0.5, gy + 0.5
                    if math.hypot(px - cx, py - cy) <= radius:
                        result = TELEPORT_TABLE.get((self.map_id, gx, gy))
                        if result is not None:
                            return result
        return None

    @staticmethod
    def resolve_spawn(dest_map_id: str, tp_gx: int, tp_gy: int):
        """Retorna (dest_map, spawn_x, spawn_y) posicionando o jogador no primeiro
        vizinho cardinal vazio (valor 0) ao redor da célula de destino (N→S→W→E).
        Se todos estiverem bloqueados usa o centro da própria célula de destino."""
        dest_map = Map(dest_map_id)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = tp_gx + dx, tp_gy + dy
            if dest_map.get(nx, ny) == 0:
                return dest_map, nx + 0.5, ny + 0.5
        return dest_map, tp_gx + 0.5, tp_gy + 0.5

    @staticmethod
    def make(map_id: str) -> "Map":
        return Map(map_id)
