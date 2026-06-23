import math
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pygame


@dataclass
class Player:
    x:       float = 2.5
    y:       float = 2.5
    dir_x:   float = 1.0
    dir_y:   float = 0.0
    plane_x: float = 0.0
    plane_y: float = 0.66


class Renderer:
    """Raycasting engine com DDA, texturas em paredes/chão e sprites billboard."""

    def __init__(self, surface: pygame.Surface, sw: int, sh: int):
        self._surf = surface
        self.sw = sw
        self.sh = sh
        self._wall_tex:     np.ndarray        = None
        self._wall_palette: List[np.ndarray] = []
        self._floor_tex:    np.ndarray        = None
        self._door_tex:     np.ndarray        = None
        self._sprite_texs:  List[np.ndarray]  = []
        self._zbuf   = np.zeros(sw, dtype=np.float64)
        self._map_np    = None  # cache numpy do mapa para AO
        self._ao_lut    = None  # lightmap de AO das paredes (estático, pré-computado)
        self._box_ao_lut = None  # lightmap de AO das caixas (separado, só chão)
        self._ao_S      = 32    # amostras por célula no lightmap
        self._horizon   = sh // 2  # centro vertical (deslocado pelo view bobbing)
        # Buffer (w, h, 3) – indexação pygame: buf[x, y] = [R, G, B]
        self._buf  = np.zeros((sw, sh, 3), dtype=np.uint8)

    # ------------------------------------------------------------------
    # Carregamento
    # ------------------------------------------------------------------

    def load_textures(self, wall_path: str, floor_path: str,
                      sprite_paths: List[str],
                      door_path: str = None,
                      wall_paths: List[str] = None) -> None:
        self._wall_tex    = self._load(wall_path)
        self._floor_tex   = self._load(floor_path)
        self._sprite_texs = [self._load(p) for p in sprite_paths]
        self._door_tex    = self._load(door_path) if door_path else self._wall_tex
        # Paleta de paredes indexada pelo código de célula:
        #   cell >= 10000 → letra_idx=(cell-10000)//100, num=(cell-10000)%100
        #   palette_idx = letra_idx*99 + (num-1)
        # wall_paths[palette_idx] é o path do brush; fallback = _wall_tex
        if wall_paths:
            self._wall_palette = [self._load(p) for p in wall_paths]
        else:
            self._wall_palette = []

    def _load(self, path: str) -> np.ndarray:
        surf = pygame.image.load(path).convert()
        return pygame.surfarray.array3d(surf)  # shape (tex_w, tex_h, 3)

    # ------------------------------------------------------------------
    # Frame público
    # ------------------------------------------------------------------

    def frame(self, game_map, player: Player,
              boxes=None, sprites=None, bob: float = 0.0) -> None:
        # Deslocamento vertical do horizonte (view bobbing / balanço da câmera).
        # Mantém o horizonte numa faixa segura para nenhum passe degenerar.
        self._horizon = int(np.clip(self.sh // 2 + round(bob), 2, self.sh - 3))
        self._render_floor_ceiling(player, game_map, boxes=boxes, sprites=sprites)
        self._render_walls(game_map, player)
        if boxes:
            self._render_boxes(player, boxes)
        if sprites:
            self._render_sprites(player, sprites)
        pygame.surfarray.blit_array(self._surf, self._buf)

    # ------------------------------------------------------------------
    # Chão e teto texturizados (vetorizado por linha com numpy)
    # ------------------------------------------------------------------

    def _render_floor_ceiling(self, p: Player, game_map, boxes=None, sprites=None) -> None:
        buf = self._buf
        ft  = self._floor_tex
        tw, th = ft.shape[0], ft.shape[1]
        sw, sh = self.sw, self.sh
        horizon = self._horizon            # centro vertical com bobbing aplicado

        lut    = self._ensure_ao_lut(game_map)
        gh, gw = lut.shape
        S      = self._ao_S

        rdx0 = p.dir_x - p.plane_x;  rdy0 = p.dir_y - p.plane_y
        rdx1 = p.dir_x + p.plane_x;  rdy1 = p.dir_y + p.plane_y

        # Linhas abaixo do horizonte = chão; acima = teto (espelhado). Com o
        # horizonte deslocado as duas regiões têm tamanhos diferentes, então
        # calculamos por "offset" a partir do horizonte e fatiamos cada lado.
        n_floor = sh - 1 - horizon          # linhas horizon+1 .. sh-1
        n_ceil  = horizon                   # linhas 0 .. horizon-1
        max_off = max(n_floor, n_ceil)

        # --- Vetorizado em blocos 2D (M offsets × sw colunas) em float32 ---
        off      = np.arange(1, max_off + 1, dtype=np.float32)      # (M,)
        row_dist = (0.5 * sh / off)[:, np.newaxis]                  # (M, 1)
        ray_x    = (rdx0 + np.arange(sw) * ((rdx1 - rdx0) / sw)).astype(np.float32)
        ray_y    = (rdy0 + np.arange(sw) * ((rdy1 - rdy0) / sw)).astype(np.float32)

        fx = np.float32(p.x) + row_dist * ray_x[np.newaxis, :]   # (M, sw)
        fy = np.float32(p.y) + row_dist * ray_y[np.newaxis, :]   # (M, sw)

        tx  = (fx * tw).astype(np.int32) % tw
        ty_ = (fy * th).astype(np.int32) % th
        colors = ft[tx, ty_]                          # (M, sw, 3)

        # --- AO do chão: amostra do lightmap pré-computado (1 lookup) ---
        iy = np.clip((fy * S).astype(np.int32), 0, gh - 1)
        ix = np.clip((fx * S).astype(np.int32), 0, gw - 1)
        shadow = lut[iy, ix]                          # (M, sw) sombra de paredes → teto

        # Sombra do chão: paredes + objetos (objetos não sombreiam o teto)
        shadow_floor = shadow.copy()
        if boxes:
            box_lut = self._ensure_box_ao_lut(boxes)
            if box_lut.shape[0] > 1:
                np.maximum(shadow_floor, box_lut[iy, ix], out=shadow_floor)
        if sprites:
            SPR_R = np.float32(0.4)
            for spr in sprites:
                dist = np.hypot(fx - np.float32(spr.x), fy - np.float32(spr.y))
                spr_shadow = np.clip(np.float32(1.0) - dist / SPR_R,
                                     np.float32(0.0), np.float32(1.0)) ** np.float32(0.5) * np.float32(0.65)
                np.maximum(shadow_floor, spr_shadow, out=shadow_floor)

        ao_floor = ((1.0 - shadow_floor) * 256.0).astype(np.uint16)[:, :, np.newaxis]
        ao_ceil  = ((1.0 - shadow       * 0.45) * 256.0).astype(np.uint16)[:, :, np.newaxis]

        cu16    = colors.astype(np.uint16)                        # (M, sw, 3)
        floor_c = ((cu16 * ao_floor) >> 8).astype(np.uint8)
        ceil_c  = (((cu16 >> 1) * ao_ceil) >> 8).astype(np.uint8)

        # buf é (sw, sh, 3) → transpõe linhas/colunas. Teto invertido em y.
        if n_floor > 0:
            buf[:, horizon + 1:sh] = np.transpose(floor_c[:n_floor], (1, 0, 2))
        if n_ceil > 0:
            buf[:, 0:horizon] = np.transpose(ceil_c[:n_ceil], (1, 0, 2))[:, ::-1, :]

        buf[:, horizon] = 85

    # ------------------------------------------------------------------
    # Paredes com DDA e texturização
    # ------------------------------------------------------------------

    def _ensure_map(self, game_map):
        if self._map_np is None:
            self._map_np = np.array(
                [[game_map.get(x, y) for x in range(game_map.width)]
                 for y in range(game_map.height)], dtype=np.int32)
        return self._map_np

    def _ensure_ao_lut(self, game_map):
        """Pré-computa o lightmap de AO do chão (depende só do mapa, não do jogador).

        shadow(wx, wy) = max(AO cardinal de contato, AO diagonal de quina).
        Calculado uma única vez numa grade S× por célula; em runtime basta amostrar.
        """
        if self._ao_lut is not None:
            return self._ao_lut
        map_np = self._ensure_map(game_map)
        mh, mw = map_np.shape
        S = self._ao_S
        AO_R    = 0.28
        FLOOR_R = AO_R * 0.75
        DARK    = 0.65

        gh, gw = mh * S, mw * S
        jj, ii = np.meshgrid(np.arange(gh), np.arange(gw), indexing='ij')
        wy = (jj + 0.5) / S
        wx = (ii + 0.5) / S
        cy = np.clip(wy.astype(np.int32), 0, mh - 1)
        cx = np.clip(wx.astype(np.int32), 0, mw - 1)
        fyf = wy - np.floor(wy)
        fxf = wx - np.floor(wx)
        cym = np.clip(cy - 1, 0, mh - 1);  cyp = np.clip(cy + 1, 0, mh - 1)
        cxm = np.clip(cx - 1, 0, mw - 1);  cxp = np.clip(cx + 1, 0, mw - 1)

        d_n = np.where(map_np[cym, cx] >= 1, fyf,       1.0)
        d_s = np.where(map_np[cyp, cx] >= 1, 1.0 - fyf, 1.0)
        d_w = np.where(map_np[cy, cxm] >= 1, fxf,       1.0)
        d_e = np.where(map_np[cy, cxp] >= 1, 1.0 - fxf, 1.0)
        shadow_card = np.clip(
            1.0 - np.minimum.reduce([d_n, d_s, d_w, d_e]) / FLOOR_R, 0.0, 1.0) ** 0.5 * DARK

        d_nw = np.where(map_np[cym, cxm] >= 1, np.hypot(fxf,       fyf),       1.0)
        d_ne = np.where(map_np[cym, cxp] >= 1, np.hypot(1.0 - fxf, fyf),       1.0)
        d_sw = np.where(map_np[cyp, cxm] >= 1, np.hypot(fxf,       1.0 - fyf), 1.0)
        d_se = np.where(map_np[cyp, cxp] >= 1, np.hypot(1.0 - fxf, 1.0 - fyf), 1.0)
        shadow_diag = np.clip(
            1.0 - np.minimum.reduce([d_nw, d_ne, d_sw, d_se]) / AO_R, 0.0, 1.0) ** 0.5 * DARK

        self._ao_lut = np.maximum(shadow_card, shadow_diag).astype(np.float32)
        return self._ao_lut

    def _ensure_box_ao_lut(self, boxes):
        """Lightmap de sombra das caixas no chão (separado do LUT de paredes).
        Aplicado apenas ao chão — caixas não sombreiam o teto.
        """
        if self._box_ao_lut is not None:
            return self._box_ao_lut
        if not boxes:
            self._box_ao_lut = np.zeros((1, 1), dtype=np.float32)
            return self._box_ao_lut
        S = self._ao_S
        gh, gw = self._ao_lut.shape
        FLOOR_R = np.float32(0.28 * 0.75)
        DARK    = np.float32(0.65)
        jj, ii = np.meshgrid(np.arange(gh), np.arange(gw), indexing='ij')
        wy = (jj + 0.5).astype(np.float32) / S
        wx = (ii + 0.5).astype(np.float32) / S
        combined = np.zeros((gh, gw), dtype=np.float32)
        for box in boxes:
            bx0 = np.float32(box.x - box.size * 0.5)
            bx1 = np.float32(box.x + box.size * 0.5)
            by0 = np.float32(box.y - box.size * 0.5)
            by1 = np.float32(box.y + box.size * 0.5)
            ddx = np.maximum(np.maximum(bx0 - wx, wx - bx1), np.float32(0.0))
            ddy = np.maximum(np.maximum(by0 - wy, wy - by1), np.float32(0.0))
            shadow_box = np.clip(np.float32(1.0) - np.hypot(ddx, ddy) / FLOOR_R,
                                 np.float32(0.0), np.float32(1.0)) ** np.float32(0.5) * DARK
            np.maximum(combined, shadow_box, out=combined)
        self._box_ao_lut = combined.astype(np.float32)
        return self._box_ao_lut

    def _render_walls(self, game_map, p: Player) -> None:
        buf    = self._buf
        # palette[0] é o brush da posição 0 no registry — textura de val==1
        # _wall_tex só é fallback se a paleta estiver vazia
        wt     = self._wall_palette[0] if self._wall_palette else self._wall_tex
        tw, th = wt.shape[0], wt.shape[1]
        sw, sh = self.sw, self.sh
        half_sh = self._horizon            # centro vertical com bobbing aplicado
        map_np  = self._ensure_map(game_map)
        mh, mw  = map_np.shape
        px, py  = p.x, p.y

        # --- Raios por coluna (vetorizado) ---
        cam = np.arange(sw, dtype=np.float64) * (2.0 / sw) - 1.0
        rdx = p.dir_x + p.plane_x * cam
        rdy = p.dir_y + p.plane_y * cam
        rdx_safe = np.where(rdx == 0.0, 1e-30, rdx)
        rdy_safe = np.where(rdy == 0.0, 1e-30, rdy)
        ddx = np.abs(1.0 / rdx_safe)
        ddy = np.abs(1.0 / rdy_safe)

        mapx = np.full(sw, int(px), dtype=np.int32)
        mapy = np.full(sw, int(py), dtype=np.int32)
        stepx = np.where(rdx < 0, -1, 1).astype(np.int32)
        stepy = np.where(rdy < 0, -1, 1).astype(np.int32)
        sdx = np.where(rdx < 0, (px - mapx) * ddx, (mapx + 1.0 - px) * ddx)
        sdy = np.where(rdy < 0, (py - mapy) * ddy, (mapy + 1.0 - py) * ddy)

        # --- DDA em lockstep: avança todos os raios até cada um achar parede ---
        hit      = np.zeros(sw, dtype=bool)
        side     = np.zeros(sw, dtype=np.int32)
        hit_type = np.zeros(sw, dtype=np.int32)   # valor da célula atingida (1=parede, 3=porta)
        for _ in range(mw + mh + 2):
            adv_x = (sdx < sdy) & ~hit
            adv_y = ~adv_x & ~hit
            mapx[adv_x] += stepx[adv_x];  sdx[adv_x] += ddx[adv_x];  side[adv_x] = 0
            mapy[adv_y] += stepy[adv_y];  sdy[adv_y] += ddy[adv_y];  side[adv_y] = 1
            cmx = np.clip(mapx, 0, mw - 1)
            cmy = np.clip(mapy, 0, mh - 1)
            cell = map_np[cmy, cmx]
            newly_hit = (cell >= 1) & ~hit
            hit_type[newly_hit] = cell[newly_hit]
            hit |= newly_hit
            if hit.all():
                break

        perp = np.where(side == 0, sdx - ddx, sdy - ddy)
        np.maximum(perp, 1e-5, out=perp)
        self._zbuf[:] = perp

        line_h = np.maximum((sh / perp).astype(np.int32), 1)
        top    = half_sh - line_h // 2                       # pode ser < 0
        draw_start = np.clip(top,               0, sh - 1)
        draw_end   = np.clip(half_sh + line_h // 2, 0, sh - 1)

        # --- Coordenada U e coluna de textura por raio ---
        wall_u = np.where(side == 0, py + perp * rdy, px + perp * rdx)
        wall_u -= np.floor(wall_u)
        tex_x  = (wall_u * tw).astype(np.int32)
        flip   = ((side == 0) & (rdx > 0)) | ((side == 1) & (rdy < 0))
        tex_x  = np.where(flip, tw - tex_x - 1, tex_x)
        np.clip(tex_x, 0, tw - 1, out=tex_x)

        # --- AO 2: aresta vertical em quinas (escalar por coluna) ---
        CORNER_R = 0.18
        corner = np.ones(sw, dtype=np.float32)
        dx0 = np.where(side == 0, mapx - stepx, mapx - 1)
        dy0 = np.where(side == 0, mapy - 1,     mapy - stepy)
        diag0 = map_np[np.clip(dy0, 0, mh - 1), np.clip(dx0, 0, mw - 1)]
        m0 = (wall_u < CORNER_R) & (diag0 >= 1)
        corner = np.where(m0, np.minimum(corner, 0.25 + 0.75 * (wall_u / CORNER_R)), corner)
        dx1 = np.where(side == 0, mapx - stepx, mapx + 1)
        dy1 = np.where(side == 0, mapy + 1,     mapy - stepy)
        diag1 = map_np[np.clip(dy1, 0, mh - 1), np.clip(dx1, 0, mw - 1)]
        m1 = ((1.0 - wall_u) < CORNER_R) & (diag1 >= 1)
        corner = np.where(m1, np.minimum(corner, 0.25 + 0.75 * ((1.0 - wall_u) / CORNER_R)), corner)

        # --- Seleciona índice de textura por coluna a partir do valor da célula ---
        # Células legadas (val==1): usa wt (textura padrão)
        # Células codificadas (val>=10000): letra_idx=(val-10000)//100, num=(val-10000)%100
        #   palette_idx = letra_idx*99 + (num-1)
        palette = self._wall_palette
        n_pal   = len(palette)
        # -1 = usar textura padrão (wt); >= 0 = índice em palette
        pal_idx = np.full(sw, -1, dtype=np.int32)
        coded   = hit_type >= 10000
        if coded.any() and n_pal > 0:
            code      = hit_type[coded] - 10000
            letra_idx = code // 100
            num       = code % 100
            raw_idx   = letra_idx * 99 + np.maximum(num - 1, 0)
            pal_idx[coded] = np.clip(raw_idx, 0, n_pal - 1)

        # --- Desenho vetorizado, limitado à faixa vertical ocupada (sw, bh) ---
        ymin = int(draw_start.min())
        ymax = int(draw_end.max())
        ys     = np.arange(ymin, ymax + 1, dtype=np.float32)[np.newaxis, :]  # (1, bh)
        lh_c   = line_h[:, np.newaxis].astype(np.float32)
        v      = (ys - top[:, np.newaxis]) / lh_c                    # (sw, bh)
        vc     = np.clip(v, 0.0, 1.0)
        inwall = (ys >= draw_start[:, np.newaxis]) & (ys <= draw_end[:, np.newaxis])

        # Inicializa todas as colunas com a textura padrão
        tex_v  = np.clip((vc * th).astype(np.int32), 0, th - 1)      # (sw, bh)
        cols   = wt[tex_x[:, np.newaxis], tex_v]                      # (sw, bh, 3) uint8

        # Sobrescreve colunas que têm textura específica da paleta
        for pidx in np.unique(pal_idx):
            if pidx < 0:
                continue  # textura padrão, já preenchida
            mask = pal_idx == pidx
            pt   = palette[pidx]
            ptw, pth = pt.shape[0], pt.shape[1]
            ptex_x = np.clip((wall_u[mask] * ptw).astype(np.int32), 0, ptw - 1)
            flip_p = ((side[mask] == 0) & (rdx[mask] > 0)) | \
                     ((side[mask] == 1) & (rdy[mask] < 0))
            ptex_x = np.where(flip_p, ptw - ptex_x - 1, ptex_x)
            ptex_v = np.clip((vc[mask] * pth).astype(np.int32), 0, pth - 1)
            cols[mask] = pt[ptex_x[:, np.newaxis], ptex_v]

        # Substitui textura de porta nas colunas que bateram em célula 3
        is_door = hit_type == 3
        if is_door.any():
            dt     = self._door_tex
            dtw, dth = dt.shape[0], dt.shape[1]
            dtex_x = np.clip((wall_u[is_door] * dtw).astype(np.int32), 0, dtw - 1)
            flip_d = ((side[is_door] == 0) & (rdx[is_door] > 0)) | \
                     ((side[is_door] == 1) & (rdy[is_door] < 0))
            dtex_x = np.where(flip_d, dtw - dtex_x - 1, dtex_x)
            dtex_v = np.clip((vc[is_door] * dth).astype(np.int32), 0, dth - 1)
            cols[is_door] = dt[dtex_x[:, np.newaxis], dtex_v]

        # paredes laterais mais escuras (inteiro)
        cols[side == 1] >>= 1

        # AO 1 — aresta inferior (contato com o chão) — em ponto-fixo uint16 (>>8)
        BASE_T  = 0.14
        ao_base = np.where(vc > 1.0 - BASE_T, 0.35 + 0.65 * (1.0 - vc) / BASE_T, 1.0)
        aoi     = (ao_base * corner[:, np.newaxis] * 256.0).astype(np.uint16)   # (sw, bh)
        cols    = ((cols.astype(np.uint16) * aoi[:, :, np.newaxis]) >> 8).astype(np.uint8)

        np.copyto(buf[:, ymin:ymax + 1], cols, where=inwall[:, :, np.newaxis])

    # ------------------------------------------------------------------
    # Caixas 3D (raycasting face a face)
    # ------------------------------------------------------------------

    def _render_boxes(self, p: Player, boxes: list) -> None:
        buf  = self._buf
        zbuf = self._zbuf
        sw, sh = self.sw, self.sh
        half = self._horizon               # centro vertical com bobbing aplicado
        px, py = p.x, p.y
        pdx, pdy, plx, ply = p.dir_x, p.dir_y, p.plane_x, p.plane_y
        inv_sw = 2.0 / sw

        # Pré-computa geometria das faces visíveis (independe da coluna x)
        ntex = len(self._sprite_texs)
        faces_data = []
        for box in boxes:
            tex = self._sprite_texs[min(box.tex_index, ntex - 1)]
            bxc, byc, bsize = box.x, box.y, box.size
            for ax, ay, bx2, by2, nx, ny in box.faces():
                if nx * (px - bxc) + ny * (py - byc) <= 0:
                    continue  # back-face culling
                # vx,vy = aresta; wx,wy = origem→a (constantes no frame)
                faces_data.append((bx2 - ax, by2 - ay, ax - px, ay - py,
                                   tex, bsize, abs(ny)))
        if not faces_data:
            return

        for x in range(sw):
            cam_x = x * inv_sw - 1.0
            rdx = pdx + plx * cam_x
            rdy = pdy + ply * cam_x

            best_t        = zbuf[x]
            best_u        = 0.0
            best_tex      = None
            best_boxh     = 1.0
            best_is_yface = False

            for vx, vy, wx, wy, tex, bsize, is_yface in faces_data:
                det = -rdx * vy + vx * rdy
                if abs(det) < 1e-8:
                    continue

                t = (-wx * vy + vx * wy) / det
                u = ( rdx * wy - rdy * wx) / det

                if t > 0.01 and 0.0 <= u <= 1.0 and t < best_t:
                    best_t        = t
                    best_u        = u
                    best_tex      = tex
                    best_boxh     = bsize
                    best_is_yface = is_yface

            if best_tex is None:
                continue

            zbuf[x] = best_t
            tw, th = best_tex.shape[0], best_tex.shape[1]

            # line_h = altura de parede completa nessa distância
            line_h = max(1, int(sh / best_t))

            # Chão da caixa = chão do mundo (same as wall bottom)
            draw_end   = min(sh - 1, half + line_h // 2)
            # Topo da caixa: eye_height=0.5, box sobe best_boxh a partir do chão
            draw_start = max(0, int(half + (0.5 - best_boxh) * line_h))

            n = draw_end - draw_start + 1
            if n <= 0:
                continue

            tex_x = max(0, min(int(best_u * tw), tw - 1))

            # Altura do mundo na linha draw_start (world_height decresce de cima p/ baixo)
            wh_start    = 0.5 - (draw_start - half) / line_h
            # V=0 no topo da caixa, V=1 no chão
            tex_v_start = (best_boxh - wh_start) / best_boxh
            tex_v_step  = 1.0 / (line_h * best_boxh)

            rows     = np.arange(n, dtype=np.float64)
            v_coords = tex_v_start + rows * tex_v_step
            tex_ys   = np.clip((v_coords * th).astype(np.int32), 0, th - 1)
            colors   = best_tex[tex_x, tex_ys].astype(np.uint16)
            if best_is_yface:
                colors >>= 1
            vc       = np.clip(v_coords, 0.0, 1.0)
            BASE_T   = 0.14
            ao_base  = np.where(vc > 1.0 - BASE_T,
                                0.35 + 0.65 * (1.0 - vc) / BASE_T, 1.0)
            aoi      = (ao_base * 256.0).astype(np.uint16)
            buf[x, draw_start:draw_end + 1] = ((colors * aoi[:, np.newaxis]) >> 8).astype(np.uint8)

    # ------------------------------------------------------------------
    # Sprites billboard com Z-buffer
    # ------------------------------------------------------------------

    def _render_sprites(self, p: Player, sprites) -> None:
        if not sprites or not self._sprite_texs:
            return

        # Mais distante primeiro (painter's algorithm)
        sorted_spr = sorted(
            sprites,
            key=lambda s: -((s.x - p.x) ** 2 + (s.y - p.y) ** 2),
        )

        inv_det = 1.0 / (p.plane_x * p.dir_y - p.dir_x * p.plane_y)
        buf     = self._buf
        zbuf    = self._zbuf
        sw, sh  = self.sw, self.sh

        for spr in sorted_spr:
            tex    = self._sprite_texs[min(spr.tex_index, len(self._sprite_texs) - 1)]
            tw, th = tex.shape[0], tex.shape[1]

            spx, spy = spr.x - p.x, spr.y - p.y
            # Transformação para espaço de câmera
            tx  =  inv_det * ( p.dir_y   * spx - p.dir_x   * spy)
            ty  =  inv_det * (-p.plane_y * spx + p.plane_x  * spy)

            if ty <= 0.01:
                continue  # atrás da câmera

            screen_x = int((sw / 2) * (1.0 + tx / ty))
            spr_h    = abs(int(sh / ty))
            spr_w    = spr_h

            horizon = self._horizon
            sy0 = max(0,      horizon - spr_h // 2)
            sy1 = min(sh - 1, horizon + spr_h // 2)
            sx0 = max(0,      screen_x - spr_w // 2)
            sx1 = min(sw - 1, screen_x + spr_w // 2)
            n_y = sy1 - sy0 + 1
            if n_y <= 0:
                continue

            spr_top = horizon - spr_h // 2
            rows    = np.arange(n_y, dtype=np.float64)
            tex_ys  = np.clip(
                ((sy0 - spr_top + rows) * th / spr_h).astype(np.int32),
                0, th - 1,
            )

            for sx in range(sx0, sx1 + 1):
                if ty >= zbuf[sx]:
                    continue  # ocluído por parede

                ttx = int((sx - (screen_x - spr_w // 2)) * tw / spr_w)
                ttx = max(0, min(ttx, tw - 1))

                colors = tex[ttx, tex_ys]               # (n_y, 3)
                mask   = np.any(colors > 10, axis=1)    # preto = transparente
                if not np.any(mask):
                    continue
                buf[sx, sy0 + np.where(mask)[0]] = colors[mask]
