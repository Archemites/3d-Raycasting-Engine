from dataclasses import dataclass


@dataclass
class Sprite:
    """Objeto no mundo renderizado como billboard (não é parede nem chão).

    x, y       -- posição no mapa (coordenadas de mapa, ex: 3.5, 5.5)
    tex_index  -- índice na lista de texturas de sprites carregada pelo Renderer
    """
    x: float
    y: float
    tex_index: int = 0
