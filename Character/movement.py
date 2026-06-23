from ursina import *
from math import sqrt


class CharacterMovement(Entity):
    """Física e movimentação WASD + pulo do personagem em primeira pessoa."""

    def __init__(
        self,
        speed: float = 5.0,
        jump_height: float = 2.5,
        gravity: float = 20.0,
        **kwargs,
    ):
        super().__init__(
            model='cube',
            visible=False,
            collider='box',
            scale=(0.8, 1.8, 0.8),
            origin_y=-0.5,   # origem nos pés; world_position == posição dos pés
            **kwargs,
        )
        self.speed = speed
        self.jump_height = jump_height
        self.gravity = gravity

        self.velocity_y: float = 0.0
        self.grounded: bool = False
        self.is_walking: bool = False

    # ------------------------------------------------------------------

    def update(self):
        self._apply_gravity()
        self._move()

    def input(self, key):
        if key == 'space' and self.grounded:
            self.velocity_y = sqrt(2.0 * self.gravity * self.jump_height)

    # ------------------------------------------------------------------

    def _apply_gravity(self):
        self.velocity_y -= self.gravity * time.dt
        self.y += self.velocity_y * time.dt

        # Ray desde a altura do joelho (0.5 u acima dos pés) até 0.15 u abaixo
        # deles — robusto contra épsilons de penetração no colisor do chão.
        ray = raycast(
            self.world_position + Vec3(0, 0.5, 0),
            Vec3(0, -1, 0),
            distance=0.65,
            ignore=(self,),
        )
        self.grounded = ray.hit
        if ray.hit and self.velocity_y <= 0:
            self.velocity_y = 0.0
            self.y = ray.world_point.y   # snap ao chão

    # ------------------------------------------------------------------

    def _move(self):
        dx = held_keys['d'] - held_keys['a']
        dz = held_keys['w'] - held_keys['s']
        self.is_walking = bool(dx or dz)

        if not self.is_walking:
            return

        # Projeta right/forward no plano horizontal e combina
        fwd = Vec3(self.forward.x, 0, self.forward.z)
        rht = Vec3(self.right.x,   0, self.right.z)
        raw = rht * dx + fwd * dz

        # Normaliza: garante velocidade idêntica em todas as direções e diagonais
        if raw.length_squared() < 1e-6:
            return
        move_dir = raw.normalized()
        step = self.speed * time.dt

        # Origem do raycast de parede: altura da cintura
        origin = self.world_position + Vec3(0, 0.9, 0)

        wall = raycast(origin, move_dir, distance=0.5, ignore=(self,))
        if not wall.hit:
            self.x += move_dir.x * step
            self.z += move_dir.z * step
        else:
            # Slide: tenta cada eixo separadamente
            if abs(move_dir.x) > 0.01:
                d = Vec3(1 if move_dir.x > 0 else -1, 0, 0)
                if not raycast(origin, d, distance=0.5, ignore=(self,)).hit:
                    self.x += move_dir.x * step

            if abs(move_dir.z) > 0.01:
                d = Vec3(0, 0, 1 if move_dir.z > 0 else -1)
                if not raycast(origin, d, distance=0.5, ignore=(self,)).hit:
                    self.z += move_dir.z * step
