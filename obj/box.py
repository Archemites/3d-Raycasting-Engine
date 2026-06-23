from dataclasses import dataclass


@dataclass
class Box:
    """Caixa 3D sólida renderizada face a face no raycasting.

    x, y      -- centro no mapa
    size      -- comprimento do lado (fração de célula; 0.4 = 40% da célula)
    tex_index -- índice na lista de texturas carregadas pelo Renderer
    """
    x: float
    y: float
    size: float = 0.4
    tex_index: int = 0

    def faces(self):
        """4 faces: (ax, ay, bx, by, normal_x, normal_y)."""
        s = self.size / 2
        cx, cy = self.x, self.y
        return (
            (cx - s, cy - s, cx + s, cy - s,  0, -1),  # norte
            (cx + s, cy + s, cx - s, cy + s,  0,  1),  # sul
            (cx + s, cy + s, cx + s, cy - s,  1,  0),  # leste
            (cx - s, cy - s, cx - s, cy + s, -1,  0),  # oeste
        )
