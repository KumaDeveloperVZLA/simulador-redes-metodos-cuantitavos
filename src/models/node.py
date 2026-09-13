"""
Modelo de Nodo de Red (Router / Switch).
Implementa la gestión de inventario con capacidad finita S, política de control (s, Q)
con lotes de admisión efectivos, cálculo de saturación de buffer y categorización
cromática para Pygame.
"""

from collections import deque
from enum import Enum
from typing import Deque, Optional, Tuple
from .packet import Packet
from ..config import (
    COLOR_NODE_NORMAL,
    COLOR_NODE_WARNING,
    COLOR_NODE_DANGER
)


class AdmissionResult(Enum):
    """
    Resultado de un intento de admisión en el buffer de un nodo.

    Es un enum (y no un bool) para poder distinguir las dos causas de pérdida:
    desbordamiento de buffer (ruptura de inventario) y bloqueo por la política
    de control de flujo (s, Q). Su valor de verdad sigue siendo booleano, de modo
    que `if node.enqueue_packet(...)` conserva la semántica original.
    """
    ADMITTED = "ADMITTED"
    OVERFLOW = "OVERFLOW"
    FLOW_CONTROL_BLOCKED = "FLOW_CONTROL_BLOCKED"

    def __bool__(self) -> bool:
        return self is AdmissionResult.ADMITTED


class RouterNode:
    """
    Representa un router o conmutador de paquetes con buffer finito.

    Política de inventario (s, Q) implementada:
      - El nodo solo admite tráfico mientras le quede saldo del último lote Q autorizado.
      - Cuando la ocupación desciende hasta el umbral s y el lote vigente se agotó,
        el nodo emite la señal de control de flujo y autoriza un nuevo lote de Q paquetes
        (equivale a "liberar el canal de entrada" hacia sus vecinos aguas arriba).
      - Si el lote se agota mientras la ocupación sigue por encima de s, el canal queda
        cerrado: el nodo ejerce contrapresión (backpressure) sobre quien intente enviarle
        paquetes, evitando llegar al desbordamiento.
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
        self.total_batches_granted: int = 0
        self.remaining_batch_credits: int = 0
        self.last_order_time: float = 0.0
        self.total_flow_control_blocks: int = 0

        # Lote inicial autorizado (el canal arranca abierto)
        self.grant_batch(0.0)

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

    # ====================================================
    # Política de inventario y control de flujo (s, Q)
    # ====================================================

    def grant_batch(self, now: float) -> None:
        """
        Emite la señal de control de flujo y autoriza un nuevo lote de Q paquetes.
        Equivale a la orden de reabastecimiento del modelo (s, Q).
        """
        self.remaining_batch_credits = self.batch_Q
        self.total_batches_granted += 1
        self.total_replenish_signals += 1
        self.last_order_time = now
        self.flow_control_signal = True

    def has_admission_credit(self) -> bool:
        """Indica si el canal de entrada del nodo está abierto (queda saldo del lote Q)."""
        return self.remaining_batch_credits > 0

    def check_flow_control(self, now: float = 0.0) -> bool:
        """
        Evalúa la política de inventario (s, Q):
        Si la ocupación desciende hasta o por debajo del umbral mínimo s y el lote
        vigente ya se consumió, emite la señal de control de flujo solicitando un
        nuevo lote de Q paquetes al canal de entrada.
        """
        if self.occupancy <= self.threshold_s:
            if self.remaining_batch_credits <= 0:
                self.grant_batch(now)
            self.flow_control_signal = True
            return True

        self.flow_control_signal = False
        return False

    # ====================================================
    # Operaciones de buffer
    # ====================================================

    def enqueue_packet(self, packet: Packet, now: float) -> AdmissionResult:
        """
        Intenta almacenar un paquete en el buffer.

        - Si la cola alcanzó la capacidad finita S, se descarta por Buffer Overflow.
        - Si el lote Q autorizado se agotó (canal cerrado), se rechaza por control de flujo.
        - En caso contrario se admite y se consume una unidad del lote vigente.
        """
        self.total_received += 1

        # Actualiza integral de área de ocupación antes del cambio
        self._update_integral_area(now)

        if len(self.buffer) >= self.capacity_S:
            # Buffer Overflow (Packet Loss / Shortage)
            self.total_dropped += 1
            packet.mark_dropped(now, reason="BUFFER_OVERFLOW")
            return AdmissionResult.OVERFLOW

        if not self.has_admission_credit():
            # Canal de entrada cerrado por la política (s, Q)
            self.total_flow_control_blocks += 1
            packet.mark_blocked(now)
            return AdmissionResult.FLOW_CONTROL_BLOCKED

        # Almacenamiento exitoso: consume una unidad del lote Q autorizado
        packet.enter_queue(now, self.node_id)
        self.buffer.append(packet)
        self.remaining_batch_credits -= 1

        # Evalúa estado de señal de control de flujo
        self.check_flow_control(now)
        return AdmissionResult.ADMITTED

    def dequeue_packet(self, now: float) -> Optional[Packet]:
        """
        Extrae el siguiente paquete en cola al INICIAR su servicio.
        A partir de este instante el paquete deja de acumular Wq (y de contar en Lq).
        """
        if not self.buffer:
            return None

        self._update_integral_area(now)
        packet = self.buffer.popleft()
        packet.exit_queue(now)
        self.total_processed += 1

        # Al vaciarse o reducirse, verificar si requiere señal de reabastecimiento (s, Q)
        self.check_flow_control(now)
        return packet

    def requeue_front(self, packet: Packet, now: float) -> None:
        """
        Reinserta al frente de la cola un paquete que terminó su servicio pero no pudo
        ser reenviado (todos los enlaces útiles caídos o vecinos con el canal cerrado).
        Es la contrapresión (backpressure) del modelo: el paquete sigue ocupando buffer
        y continúa acumulando espera en cola.
        """
        self._update_integral_area(now)
        packet.enter_queue(now, self.node_id)
        self.buffer.appendleft(packet)
        self.total_processed = max(0, self.total_processed - 1)
        self.check_flow_control(now)

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
