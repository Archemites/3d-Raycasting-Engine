from ursina import *


class CharacterCamera(Entity):
    """Controla a câmera FPS: yaw via rotação do player, pitch local neste pivot.
    Aplica o offset de view bobbing calculado por CharacterVisual.
    """

    def __init__(
        self,
        player,
        sensitivity: float = 40.0,
        **kwargs,
    ):
        super().__init__(
            parent=player,
            y=1.7,
            **kwargs,
        )
        self.player = player
        self.sensitivity = sensitivity
        self._pitch: float = 0.0

        # Estado do bob — preenchido por CharacterVisual a cada frame
        self.bob_x: float = 0.0
        self.bob_y: float = 0.0

        camera.parent = self
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)

        mouse.locked = True
        mouse.visible = False

    # ------------------------------------------------------------------

    def update(self):
        if not mouse.locked:
            return

        self.player.rotation_y += mouse.velocity[0] * self.sensitivity

        self._pitch = clamp(
            self._pitch - mouse.velocity[1] * self.sensitivity,
            -89.0,
            89.0,
        )
        self.rotation_x = self._pitch

        # Aplica o offset de bobbing calculado por CharacterVisual
        camera.position = Vec3(self.bob_x, self.bob_y, 0)

    # ------------------------------------------------------------------

    def toggle_cursor(self):
        mouse.locked = not mouse.locked
        mouse.visible = not mouse.visible
