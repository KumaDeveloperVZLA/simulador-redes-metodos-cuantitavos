"""
Modelo de Paquete de Datos.
Encapsula los tiempos de ciclo de vida para el cómputo de métricas de Teoría de Colas
y coordenadas de animación interpolada para la interfaz de Pygame.
"""

from enum import Enum
from typing import Optional, Tuple, List


class PacketStatus(Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    IN_SERVICE = "IN_SERVICE"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"
    BLOCKED = "BLOCKED"


class Packet:
    """
    Representa un paquete discreto que transita por la red.
    """

    def __init__(
        self,
        packet_id: int,
        source_id: str,
        destination_id: str,
        creation_time: float
    ):
        self.packet_id: int = packet_id
        self.source_id: str = source_id
        self.destination_id: str = destination_id
        self.creation_time: float = creation_time

        # Tiempos de control de colas y tránsito
        self.current_queue_enter_time: float = creation_time
        self.total_queue_wait_time: float = 0.0
        self.total_service_time: float = 0.0
        self.completion_time: Optional[float] = None
        self.drop_time: Optional[float] = None

        # Estado y ruta
        self.status: PacketStatus = PacketStatus.CREATED
        self.current_node_id: Optional[str] = source_id
        self.current_link_id: Optional[str] = None
        self.path_history: List[str] = [source_id]

        # Asignación vigente calculada por el Algoritmo Húngaro.
        # Solo es válida hasta assignment_expiry: pasado ese instante la foto de
        # saturación con la que se resolvió la matriz ya no representa a la red.
        self.assigned_link_id: Optional[str] = None
        self.assignment_expiry: float = -1.0

        # Trazabilidad de fin de vida del paquete
        self.drop_reason: Optional[str] = None
        self.delivered_to_id: Optional[str] = None

        # Atributos para animación visual (LERP en Pygame)
        self.transit_start_time: float = 0.0
        self.transit_duration: float = 0.1
        self.start_pos: Tuple[float, float] = (0.0, 0.0)
        self.end_pos: Tuple[float, float] = (0.0, 0.0)
        self.visual_progress: float = 0.0

    def enter_queue(self, now: float, node_id: str) -> None:
        """Registra el ingreso a la cola de un nodo."""
        self.status = PacketStatus.QUEUED
        self.current_node_id = node_id
        self.current_queue_enter_time = now
        if node_id not in self.path_history:
            self.path_history.append(node_id)

    def exit_queue(self, now: float) -> float:
        """
        Registra la salida de la cola en el instante en que COMIENZA el servicio
        y acumula Wq (espera en cola, sin incluir el tiempo de servicio 1/mu).
        """
        wait = max(0.0, now - self.current_queue_enter_time)
        self.total_queue_wait_time += wait
        self.status = PacketStatus.IN_SERVICE
        return wait

    def add_service_time(self, duration: float) -> None:
        """Acumula el tiempo de servicio exponencial consumido en un nodo."""
        self.total_service_time += max(0.0, duration)

    def start_transit(
        self,
        now: float,
        link_id: str,
        duration: float,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float]
    ) -> None:
        """Inicia el desplazamiento visual a través de un enlace."""
        self.status = PacketStatus.IN_TRANSIT
        self.current_link_id = link_id
        self.transit_start_time = now
        self.transit_duration = max(0.01, duration)
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.visual_progress = 0.0

    def update_visual_progress(self, current_sim_time: float) -> float:
        """Calcula el progreso LERP (0.0 a 1.0) para el renderizado."""
        if self.status != PacketStatus.IN_TRANSIT:
            return 1.0
        elapsed = current_sim_time - self.transit_start_time
        self.visual_progress = min(1.0, max(0.0, elapsed / self.transit_duration))
        return self.visual_progress

    def get_current_coords(self) -> Tuple[float, float]:
        """Obtiene las coordenadas (x, y) interpoladas linealmente (LERP)."""
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * self.visual_progress
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * self.visual_progress
        return (x, y)

    def mark_completed(self, now: float, egress_id: Optional[str] = None) -> None:
        """Marca el paquete como entregado exitosamente en un nodo de salida."""
        self.status = PacketStatus.COMPLETED
        self.completion_time = now
        self.delivered_to_id = egress_id
        self.visual_progress = 1.0

    @property
    def was_misrouted(self) -> bool:
        """True si el paquete se entregó en un egress distinto al destino asignado."""
        return (
            self.delivered_to_id is not None
            and self.delivered_to_id != self.destination_id
        )

    def mark_dropped(self, now: float, reason: str = "BUFFER_OVERFLOW") -> None:
        """Marca el paquete como descartado por desbordamiento."""
        self.status = PacketStatus.DROPPED
        self.drop_time = now
        self.drop_reason = reason
        self.visual_progress = 1.0

    def mark_blocked(self, now: float) -> None:
        """
        Marca el paquete como rechazado por la política de control de flujo (s, Q):
        el nodo agotó el lote Q autorizado y su ocupación sigue por encima del
        umbral s, por lo que no libera el canal de entrada.
        """
        self.status = PacketStatus.BLOCKED
        self.drop_time = now
        self.drop_reason = "FLOW_CONTROL"
        self.visual_progress = 1.0

    @property
    def total_system_time(self) -> float:
        """Tiempo medio de estancia total W (espera + transmisión)."""
        if self.completion_time is not None:
            return max(0.0, self.completion_time - self.creation_time)
        return 0.0
