import math
import os
import sys

import pygame

from mapa.map import Map
from obj.box import Box
from render.renderer import Player, Renderer

_TEX_DIR      = os.path.join(os.path.dirname(__file__), "textures")
_BRUSH_FILE   = os.path.join(_TEX_DIR, "_brushes.txt")
_TEX_DEFAULTS = {
    "wall":  os.path.join(_TEX_DIR, "wall.png"),
    "floor": os.path.join(_TEX_DIR, "floor.png"),
    "door":  os.path.join(_TEX_DIR, "door.png"),
    "box":   os.path.join(_TEX_DIR, "box.png"),
}


def _active_textures() -> dict[str, str]:
    """Lê _brushes.txt e retorna o brush marcado com * por categoria."""
    result = dict(_TEX_DEFAULTS)
    if not os.path.isfile(_BRUSH_FILE):
        return result
    try:
        with open(_BRUSH_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                if not line.startswith("*"):
                    continue
                rest = line[1:]
                parts = rest.split("|", 1)
                if len(parts) != 2:
                    continue
                cat, path = parts[0].strip(), parts[1].strip()
                if cat in result and os.path.isfile(path):
                    result[cat] = path
    except Exception:
        pass
    return result


def _wall_palette_paths() -> list[str]:
    """
    Retorna lista ordenada de todos os wall brushes do registry (posição 0-based).

    O valor de célula codifica a posição: cell = 10000 + letra_idx*100 + num,
    palette_idx = letra_idx*99 + (num-1).
    O renderer usa esta lista diretamente como _wall_palette[0..N].
    """
    paths = []
    if not os.path.isfile(_BRUSH_FILE):
        return paths
    try:
        with open(_BRUSH_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                rest  = line[1:] if line[0] in ("*", " ") else line
                parts = rest.split("|", 1)
                if len(parts) != 2:
                    continue
                cat, path = parts[0].strip(), parts[1].strip()
                if cat == "wall" and os.path.isfile(path):
                    paths.append(path)
    except Exception:
        pass
    return paths

SCREEN_W   = 800
SCREEN_H   = 600
MOVE_SPD   = 0.12
ROT_SPD    = 0.07
MOUSE_SENS = 0.003

BOB_FREQ   = 0.26    # fase por frame andando
BOB_AMP    = 0.015   # amplitude máxima (fração da altura interna) — sutil
BOB_SMOOTH = 0.14    # suavização lerp ao começar/parar
BOB_INIT   = 40      # intensidade padrão 0-100

QUALITY_STEPS = [
    (160, 120),
    (200, 150),
    (256, 192),
    (320, 240),
    (400, 300),
    (480, 360),
]
QUALITY_INIT = 3  # 320×240


# ---------------------------------------------------------------------------

def _fit_rect(sw: int, sh: int, tw: int, th: int) -> pygame.Rect:
    s = min(sw / tw, sh / th)
    w, h = int(tw * s), int(th * s)
    return pygame.Rect((sw - w) // 2, (sh - h) // 2, w, h)


def _build_renderer(rw: int, rh: int):
    surf = pygame.Surface((rw, rh))
    r = Renderer(surf, rw, rh)
    tex          = _active_textures()
    wall_palette = _wall_palette_paths()  # lista completa, posição = palette_idx
    r.load_textures(tex["wall"], tex["floor"], [tex["box"]],
                    door_path=tex["door"], wall_paths=wall_palette)
    return surf, r


def _draw_slider(screen, font_med, font_sm,
                 label: str, lo_txt: str, hi_txt: str,
                 cx: int, cy: int, track_w: int,
                 value: float, v_min: float, v_max: float,
                 val_fmt: str, stepped: bool, n_steps: int,
                 dragging: bool) -> None:
    """Desenha um slider genérico. value em [v_min, v_max]."""
    t = (value - v_min) / (v_max - v_min)
    track_x = cx - track_w // 2

    # Rótulo acima
    lbl = font_med.render(label + val_fmt, True, (210, 210, 210))
    screen.blit(lbl, lbl.get_rect(center=(cx, cy - 34)))

    # Trilha
    pygame.draw.rect(screen, (80, 80, 80),
                     pygame.Rect(track_x, cy - 4, track_w, 8), border_radius=4)

    # Marcas de passo (só em sliders discretos)
    if stepped:
        for i in range(n_steps):
            lx = track_x + int(i / (n_steps - 1) * track_w)
            pygame.draw.line(screen, (140, 140, 140), (lx, cy - 8), (lx, cy + 8), 1)

    # Handle
    hx = track_x + int(t * track_w)
    col = (80, 180, 255) if dragging else (255, 255, 255)
    pygame.draw.circle(screen, col, (hx, cy), 13)
    pygame.draw.circle(screen, (40, 40, 40), (hx, cy), 13, 2)

    # Extremos
    lo = font_sm.render(lo_txt, True, (140, 140, 140))
    hi = font_sm.render(hi_txt, True, (140, 140, 140))
    screen.blit(lo, lo.get_rect(midtop=(track_x, cy + 18)))
    screen.blit(hi, hi.get_rect(midtop=(track_x + track_w, cy + 18)))


def _draw_pause(screen: pygame.Surface, quality_idx: int, bob_intensity: int,
                dragging_which) -> None:
    sw, sh = screen.get_size()

    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    font_big = pygame.font.SysFont(None, 72)
    font_med = pygame.font.SysFont(None, 36)
    font_sm  = pygame.font.SysFont(None, 26)

    title = font_big.render("PAUSED", True, (255, 255, 255))
    screen.blit(title, title.get_rect(center=(sw // 2, sh // 5)))

    track_w = int(sw * 0.55)
    cx = sw // 2

    rw, rh = QUALITY_STEPS[quality_idx]
    _draw_slider(
        screen, font_med, font_sm,
        label="Qualidade: ", lo_txt="Baixo", hi_txt="Alto",
        cx=cx, cy=sh // 2 - 20, track_w=track_w,
        value=quality_idx, v_min=0, v_max=len(QUALITY_STEPS) - 1,
        val_fmt=f"{rw}×{rh}",
        stepped=True, n_steps=len(QUALITY_STEPS),
        dragging=(dragging_which == 'quality'),
    )

    _draw_slider(
        screen, font_med, font_sm,
        label="Balanço: ", lo_txt="0", hi_txt="100",
        cx=cx, cy=sh // 2 + 90, track_w=track_w,
        value=bob_intensity, v_min=0, v_max=100,
        val_fmt=str(bob_intensity),
        stepped=False, n_steps=0,
        dragging=(dragging_which == 'bob'),
    )

    hint = font_sm.render("ESC — retomar    Q — sair    F11 — fullscreen",
                           True, (160, 160, 160))
    screen.blit(hint, hint.get_rect(center=(sw // 2, sh * 7 // 8)))


def _on_track(mx, my, track_x, track_y, track_w, margin=22) -> bool:
    return track_x <= mx <= track_x + track_w and abs(my - track_y) < margin


def _draw_interact_prompt(screen: pygame.Surface) -> None:
    sw, sh = screen.get_size()
    font_key  = pygame.font.SysFont(None, 52)
    font_text = pygame.font.SysFont(None, 36)

    key_surf  = font_key.render("E", True, (240, 220, 60))
    text_surf = font_text.render("Interagir", True, (220, 220, 220))

    pad = 14
    key_w,  key_h  = key_surf.get_size()
    txt_w,  txt_h  = text_surf.get_size()
    gap = 12
    total_w = key_w + gap + txt_w + pad * 2
    total_h = max(key_h, txt_h) + pad * 2

    cx = sw // 2
    cy = sh * 3 // 4

    bg = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    pygame.draw.rect(bg, (180, 160, 40, 200),
                     pygame.Rect(0, 0, total_w, total_h), 2, border_radius=8)
    screen.blit(bg, (cx - total_w // 2, cy - total_h // 2))

    # caixa da tecla E
    key_box_size = key_h + 8
    key_box_rect = pygame.Rect(cx - total_w // 2 + pad,
                               cy - key_box_size // 2,
                               key_box_size, key_box_size)
    pygame.draw.rect(screen, (60, 55, 20), key_box_rect, border_radius=5)
    pygame.draw.rect(screen, (220, 190, 50), key_box_rect, 2, border_radius=5)
    screen.blit(key_surf, key_surf.get_rect(center=key_box_rect.center))

    screen.blit(text_surf, text_surf.get_rect(
        midleft=(key_box_rect.right + gap, cy)))


# ---------------------------------------------------------------------------

def main() -> None:
    pygame.init()

    fullscreen    = False
    paused        = False
    dragging_which = None   # None | 'quality' | 'bob'
    quality_idx   = QUALITY_INIT
    bob_intensity = BOB_INIT  # 0-100

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Raycaster")
    clock = pygame.time.Clock()

    game_map = Map("A")
    player = Player(x=2.5, y=2.5, dir_x=1.0, dir_y=0.0, plane_x=0.0, plane_y=0.66)

    def _boxes_from_map(m):
        out = []
        for d in m.boxes:
            shape = d.get("shape", "square") if isinstance(d, dict) else "square"
            x     = d["x"]    if isinstance(d, dict) else d.x
            y     = d["y"]    if isinstance(d, dict) else d.y
            size  = d.get("size", 0.5) if isinstance(d, dict) else d.size
            ti    = d.get("tex_index", 0) if isinstance(d, dict) else getattr(d, "tex_index", 0)
            out.append(Box(x, y, size=size, tex_index=ti))
        if not out:
            out = [
                Box(3.5,  5.5,  size=0.5),
                Box(7.5,  7.5,  size=0.5),
                Box(10.5, 3.5,  size=0.5),
                Box(12.5, 12.5, size=0.5),
            ]
        return out

    boxes = _boxes_from_map(game_map)
    tp_cooldown   = 0    # frames de imunidade após teleporte
    near_tp       = None # destino do TP próximo (ou None)

    rw, rh = QUALITY_STEPS[quality_idx]
    render_surf, renderer = _build_renderer(rw, rh)

    bob_phase = 0.0
    bob_cur   = 0.0

    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    while True:
        sw, sh = screen.get_size()
        track_w  = int(sw * 0.55)
        track_x  = (sw - track_w) // 2
        q_cy     = sh // 2 - 20    # centro Y do slider de qualidade
        bob_cy   = sh // 2 + 90    # centro Y do slider de balanço

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    paused = not paused
                    if paused:
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                    else:
                        pygame.mouse.get_rel()
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)

                if ev.key == pygame.K_q and paused:
                    pygame.quit()
                    sys.exit()

                if ev.key == pygame.K_e and not paused and near_tp is not None and tp_cooldown == 0:
                    dest_map_id, tp_gx, tp_gy = near_tp
                    game_map, spawn_x, spawn_y = Map.resolve_spawn(dest_map_id, tp_gx, tp_gy)
                    player.x, player.y = spawn_x, spawn_y
                    boxes = _boxes_from_map(game_map)
                    renderer._map_np = None
                    renderer._ao_lut = None
                    tp_cooldown = 60
                    near_tp = None

                if ev.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    screen = pygame.display.set_mode(
                        (0, 0) if fullscreen else (SCREEN_W, SCREEN_H),
                        pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE,
                    )

            if paused:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if _on_track(mx, my, track_x, q_cy, track_w):
                        dragging_which = 'quality'
                        n = len(QUALITY_STEPS) - 1
                        new_idx = max(0, min(n, round((mx - track_x) / track_w * n)))
                        if new_idx != quality_idx:
                            quality_idx = new_idx
                            rw, rh = QUALITY_STEPS[quality_idx]
                            render_surf, renderer = _build_renderer(rw, rh)
                    elif _on_track(mx, my, track_x, bob_cy, track_w):
                        dragging_which = 'bob'
                        bob_intensity = max(0, min(100, round((mx - track_x) / track_w * 100)))

                if ev.type == pygame.MOUSEMOTION and dragging_which:
                    mx = ev.pos[0]
                    if dragging_which == 'quality':
                        n = len(QUALITY_STEPS) - 1
                        new_idx = max(0, min(n, round((mx - track_x) / track_w * n)))
                        if new_idx != quality_idx:
                            quality_idx = new_idx
                            rw, rh = QUALITY_STEPS[quality_idx]
                            render_surf, renderer = _build_renderer(rw, rh)
                    elif dragging_which == 'bob':
                        bob_intensity = max(0, min(100, round((mx - track_x) / track_w * 100)))

                if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    dragging_which = None

        # ------------------------------------------------------------------
        if not paused:
            keys = pygame.key.get_pressed()
            start_x, start_y = player.x, player.y

            def blocked(x, y):
                if game_map.get(int(x), int(y)) != 0:
                    return True
                for b in boxes:
                    s = b.size / 2 + 0.2
                    if abs(x - b.x) < s and abs(y - b.y) < s:
                        return True
                return False

            if keys[pygame.K_w] or keys[pygame.K_UP]:
                nx = player.x + player.dir_x * MOVE_SPD
                ny = player.y + player.dir_y * MOVE_SPD
                if not blocked(nx, player.y): player.x = nx
                if not blocked(player.x, ny): player.y = ny

            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                nx = player.x - player.dir_x * MOVE_SPD
                ny = player.y - player.dir_y * MOVE_SPD
                if not blocked(nx, player.y): player.x = nx
                if not blocked(player.x, ny): player.y = ny

            def rotate(angle: float) -> None:
                c, s = math.cos(angle), math.sin(angle)
                player.dir_x,   player.dir_y   = (player.dir_x * c - player.dir_y * s,
                                                   player.dir_x * s + player.dir_y * c)
                player.plane_x, player.plane_y = (player.plane_x * c - player.plane_y * s,
                                                   player.plane_x * s + player.plane_y * c)

            if keys[pygame.K_LEFT]:  rotate(-ROT_SPD)
            if keys[pygame.K_RIGHT]: rotate( ROT_SPD)

            mx, _ = pygame.mouse.get_rel()
            if mx:
                rotate(mx * MOUSE_SENS)

            if keys[pygame.K_a]:
                nx = player.x + player.dir_y * MOVE_SPD
                ny = player.y - player.dir_x * MOVE_SPD
                if not blocked(nx, player.y): player.x = nx
                if not blocked(player.x, ny): player.y = ny

            if keys[pygame.K_d]:
                nx = player.x - player.dir_y * MOVE_SPD
                ny = player.y + player.dir_x * MOVE_SPD
                if not blocked(nx, player.y): player.x = nx
                if not blocked(player.x, ny): player.y = ny

            moved = (player.x - start_x) ** 2 + (player.y - start_y) ** 2 > 1e-9
            if moved and bob_intensity > 0:
                bob_phase += BOB_FREQ
                target = math.sin(bob_phase) * (rh * BOB_AMP * bob_intensity / 100.0)
            else:
                target = 0.0
            bob_cur += (target - bob_cur) * BOB_SMOOTH

            # Detecta portal próximo para exibir prompt
            if tp_cooldown > 0:
                tp_cooldown -= 1
                near_tp = None
            else:
                near_tp = game_map.near_teleport(player.x, player.y)

            renderer.frame(game_map, player, boxes=boxes, bob=bob_cur)

        # ------------------------------------------------------------------
        dest = _fit_rect(sw, sh, rw, rh)
        dest = dest.clip(screen.get_rect())
        if dest.size != (sw, sh):
            screen.fill((0, 0, 0))
        if dest.width > 0 and dest.height > 0:
            scaled = pygame.transform.scale(render_surf, dest.size)
            screen.blit(scaled, dest.topleft)

        if not paused and near_tp is not None and tp_cooldown == 0:
            _draw_interact_prompt(screen)

        if paused:
            _draw_pause(screen, quality_idx, bob_intensity, dragging_which)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
