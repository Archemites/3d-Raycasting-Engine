from ursina import *
import math


class CharacterVisual(Entity):
    """Calcula o estado de view bobbing e envia o offset para CharacterCamera aplicar.

    cam_controller: instância de CharacterCamera (não o objeto camera global).
    """

    def __init__(
        self,
        player,
        cam_controller,
        bob_frequency: float = 5.0,
        bob_amplitude: float = 0.14,
        smooth_speed: float = 6.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.player = player
        self._ctrl = cam_controller

        self.bob_frequency = bob_frequency
        self.bob_amplitude = bob_amplitude
        self.smooth_speed = smooth_speed

        self._bob_time: float = 0.0
        self._cur_x: float = 0.0
        self._cur_y: float = 0.0

    # ------------------------------------------------------------------

    def update(self):
        if self.player.is_walking and self.player.grounded:
            self._bob_time += time.dt * self.bob_frequency
            target_x = math.sin(self._bob_time) * self.bob_amplitude * 0.5
            target_y = abs(math.sin(self._bob_time * 2.0)) * self.bob_amplitude
        else:
            target_x = 0.0
            target_y = 0.0

        t = min(time.dt * self.smooth_speed, 1.0)
        self._cur_x = lerp(self._cur_x, target_x, t)
        self._cur_y = lerp(self._cur_y, target_y, t)

        # CharacterCamera lê estes valores e aplica em camera.position
        self._ctrl.bob_x = self._cur_x
        self._ctrl.bob_y = self._cur_y
