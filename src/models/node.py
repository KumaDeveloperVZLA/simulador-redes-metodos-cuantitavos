"""
Modelo de Nodo de Red (Router / Switch).
Implementa la gestión de inventario con capacidad finita S, política de control (s, Q),
cálculo de saturación de buffer y categorización cromática para Pygame.
"""

from collections import deque
from typing import Deque, Optional, Tuple
from .packet import Packet, PacketStatus
from ..config import (
    COLOR_NODE_NORMAL,
    COLOR_NODE_WARNING,
    COLOR_NODE_DANGER
)


class RouterNode:
    """
    Representa un router o conmutador de paquetes con buffer finito.
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        pos: Tuple[int, int],
        capacity_S: int = 50,
        threshold_s: int = 10,
        batch_Q: int = 15,
        is_ingress: bool = False,
        is_egress: bool = False
    ):
        self.node_id: str = node_id
        self.name: str = name
        self.pos: Tuple[int, int] = pos
        self.capacity_S: int = capacity_S
        self.threshold_s: int = threshold_s
        self.batch_Q: int = batch_Q
        self.is_ingress: bool = is_ingress
        self.is_egress: bool = is_egress

        # Cola de paquetes (Buffer)
        self.buffer: Deque[Packet] = deque()

        # Servidor SimPy asignado dinámicamente en el motor
        self.server_resource = None

        # Control de inventario y reabastecimiento (s, Q)
        self.flow_control_signal: bool = False
        self.total_replenish_signals: int = 0

        # Métricas locales del nodo
        self.total_received: int = 0
        self.total_processed: int = 0
        self.total_dropped: int = 0

        # Historial de ocupación para cálculo de Lq local
        self.last_state_change_time: float = 0.0
        self.accumulated_area_lq: float = 0.0

    @property
    def occupancy(self) -> int:
        """Número de paquetes actualmente retenidos en la cola del buffer."""
        return len(self.buffer)

    @property
    def saturation(self) -> float:
        """Proporción de saturación del buffer (0.0 a 1.0)."""
        if self.capacity_S <= 0:
            return 0.0
        return min(1.0, len(self.buffer) / self.capacity_S)

    def get_color_category(self) -> Tuple[int, int, int]:
        """
        Retorna el color según los rangos del requerimiento:
        - Verde: < 50%
        - Amarillo: 50% - 80%
        - Rojo: > 80%
        """
        sat = self.saturation
        if sat < 0.50:
            return COLOR_NODE_NORMAL
        elif sat <= 0.80:
            return COLOR_NODE_WARNING
        else:
            return COLOR_NODE_DANGER

    def check_flow_control(self) -> bool:
        """
        Evalúa la política de inventario (s, Q):
        Si la ocupación desciende por debajo del umbral mínimo s,
        activa la señal de control de flujo para solicitar un lote Q.
        """
        if self.occupancy <= self.threshold_s:
            if not self.flow_control_signal:
                self.flow_control_signal = True
                self.total_replenish_signals += 1
            return True
        else:
            self.flow_control_signal = False
            return False

    def enqueue_packet(self, packet: Packet, now: float) -> bool:
        """
        Intenta almacenar un paquete en el buffer.
        Si la cola ha alcanzado la capacidad finita S, se descarta por Buffer Overflow.
        Retorna True si fue aceptado, False si fue descartado.
        """
        self.total_received += 1

        # Actualiza integral de área de ocupación antes del cambio
        self._update_integral_area(now)

        if len(self.buffer) >= self.capacity_S:
            # Buffer Overflow (Packet Loss / Shortage)
            self.total_dropped += 1
            packet.mark_dropped(now, reason="BUFFER_OVERFLOW")
            return False

        # Almacenamiento exitoso
        packet.enter_queue(now, self.node_id)
        self.buffer.append(packet)

        # Evalúa estado de señal de control de flujo
        self.check_flow_control()
        return True

    def dequeue_packet(self, now: float) -> Optional[Packet]:
        """
        Extrae el siguiente paquete en cola para servicio o reenvío.
        """
        if not self.buffer:
            return None

        self._update_integral_area(now)
        packet = self.buffer.popleft()
        packet.exit_queue(now)
        self.total_processed += 1

        # Al vaciarse o reducirse, verificar si requiere señal de reabastecimiento (s, Q)
        self.check_flow_control()
        return packet

    def _update_integral_area(self, now: float) -> None:
        """Actualiza el área acumulada para el promedio ponderado de ocupación."""
        dt = max(0.0, now - self.last_state_change_time)
        self.accumulated_area_lq += len(self.buffer) * dt
        self.last_state_change_time = now

    def get_time_weighted_lq(self, total_time: float) -> float:
        """Obtiene el promedio temporal Lq para este nodo."""
        if total_time <= 0:
            return 0.0
        # Incluir hasta el instante actual
        dt = max(0.0, total_time - self.last_state_change_time)
        total_area = self.accumulated_area_lq + (len(self.buffer) * dt)
        return total_area / total_time
