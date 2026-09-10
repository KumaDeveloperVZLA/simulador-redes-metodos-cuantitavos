"""
Modelo de Enlace de Red (Network Link).
Administra latencias dinámicas, estado activo/inactivo (falla de enlace) y detección de clicks.
"""

import math
from typing import List, Tuple
from .packet import Packet
from ..config import (
    COLOR_LINK_ACTIVE,
    COLOR_LINK_DOWN,
    COLOR_LINK_CONGESTED
)


class NetworkLink:
    """
    Representa un canal o enlace de comunicación bidireccional o dirigido entre dos nodos.
    """

    def __init__(
        self,
        link_id: str,
        source_id: str,
        target_id: str,
        base_latency: float = 0.05,
        bandwidth: float = 50.0
    ):
        self.link_id: str = link_id
        self.source_id: str = source_id
        self.target_id: str = target_id
        self.base_latency: float = base_latency
        self.bandwidth: float = bandwidth

        # Estado del enlace (interactivo vía click del usuario)
        self.is_active: bool = True
        self.packets_in_transit: List[Packet] = []
        self.total_transmitted: int = 0
        self.failure_toggle_count: int = 0

    @property
    def current_latency(self) -> float:
        """
        Latencia dinámica del enlace:
        Si el enlace está caído, la latencia es prácticamente infinita (penalización máxima).
        Si está activo, considera la latencia base más un componente de retardo por congestión.
        """
        if not self.is_active:
            return 10000.0  # Penalización severa para el algoritmo Húngaro

        # Retardo por paquetes en tránsito simultáneo
        congestion_delay = 0.005 * len(self.packets_in_transit)
        return self.base_latency + congestion_delay

    def toggle_state(self) -> bool:
        """Alterna el estado del enlace entre activo y caído (simulación de fallo)."""
        self.is_active = not self.is_active
        self.failure_toggle_count += 1
        return self.is_active

    def get_color(self) -> Tuple[int, int, int]:
        """Color representativo del enlace según su condición operativa."""
        if not self.is_active:
            return COLOR_LINK_DOWN
        if len(self.packets_in_transit) > 5:
            return COLOR_LINK_CONGESTED
        return COLOR_LINK_ACTIVE

    @staticmethod
    def distance_point_to_segment(
        px: float, py: float,
        x1: float, y1: float,
        x2: float, y2: float
    ) -> float:
        """
        Calcula la distancia mínima entre un punto (cursor del mouse)
        y el segmento de recta del enlace (x1, y1) -> (x2, y2).
        """
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(px - x1, py - y1)

        # Proyección escalar normalizada sobre el segmento [0, 1]
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)
