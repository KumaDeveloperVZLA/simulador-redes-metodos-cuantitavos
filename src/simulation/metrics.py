"""
Módulo de Métricas y Métodos Cuantitativos.
Cómputo en tiempo real de Líneas de Espera (L, Lq, W, Wq) y Modelo de Costos de Inventario
(Holding Cost integral y Shortage / Ruptura por Buffer Overflow).
"""

from typing import Dict, Any, List
from ..config import (
    HOLDING_COST_RATE_H,
    SHORTAGE_PENALTY_COST
)


class MetricsTracker:
    """
    Rastrea y consolida las métricas cuantitativas de la simulación de red.
    """

    def __init__(
        self,
        holding_cost_rate: float = HOLDING_COST_RATE_H,
        shortage_cost_penalty: float = SHORTAGE_PENALTY_COST
    ):
        self.holding_cost_rate: float = holding_cost_rate
        self.shortage_cost_penalty: float = shortage_cost_penalty

        # Contadores de paquetes
        self.total_generated: int = 0
        self.total_processed: int = 0
        self.total_dropped: int = 0          # Pérdidas por desbordamiento de buffer
        self.total_blocked: int = 0          # Rechazos por control de flujo (s, Q)
        self.total_link_failures: int = 0    # Perdidos en tránsito por caída del enlace
        self.total_misrouted: int = 0        # Entregados en un egress distinto al destino

        # Tiempos acumulados para discretos W y Wq
        self.sum_queue_wait_time: float = 0.0
        self.sum_system_time: float = 0.0

        # Áreas integrales para promedio ponderado en el tiempo L y Lq
        self.last_update_time: float = 0.0
        self.integral_area_lq: float = 0.0
        self.integral_area_l: float = 0.0

        # Estado actual instantáneo del sistema
        self.current_packets_in_queue: int = 0
        self.current_packets_in_system: int = 0

        # Costos acumulados
        self.accumulated_holding_cost: float = 0.0
        self.accumulated_shortage_cost: float = 0.0

    def record_packet_generation(self, now: float) -> None:
        """Registra la creación de un nuevo paquete por el proceso Poisson."""
        self.update_integrals(now)
        self.total_generated += 1
        self.current_packets_in_system += 1

    def record_packet_enqueue(self, now: float) -> None:
        """Registra el ingreso de un paquete a un buffer de espera."""
        self.update_integrals(now)
        self.current_packets_in_queue += 1

    def record_packet_dequeue(self, now: float) -> None:
        """Registra la extracción de un paquete del buffer para inicio de transmisión."""
        self.update_integrals(now)
        if self.current_packets_in_queue > 0:
            self.current_packets_in_queue -= 1

    def record_packet_completed(
        self,
        now: float,
        total_wait_time: float,
        total_system_time: float,
        misrouted: bool = False
    ) -> None:
        """Registra la entrega exitosa de un paquete en el nodo destino."""
        self.update_integrals(now)
        self.total_processed += 1
        if misrouted:
            self.total_misrouted += 1
        if self.current_packets_in_system > 0:
            self.current_packets_in_system -= 1

        self.sum_queue_wait_time += max(0.0, total_wait_time)
        self.sum_system_time += max(0.0, total_system_time)

    def record_packet_dropped(self, now: float) -> None:
        """Registra un descarte de paquete por Buffer Overflow (Ruptura)."""
        self.update_integrals(now)
        self.total_dropped += 1
        if self.current_packets_in_system > 0:
            self.current_packets_in_system -= 1

        # Suma penalización monetaria de ruptura fija
        self.accumulated_shortage_cost += self.shortage_cost_penalty

    def record_packet_lost_in_transit(self, now: float) -> None:
        """
        Registra un paquete perdido porque el enlace por el que viajaba se cayó.
        No es un desbordamiento de buffer: se contabiliza aparte para no contaminar
        la métrica de Overflow del reporte, pero también penaliza como ruptura.
        """
        self.update_integrals(now)
        self.total_link_failures += 1
        if self.current_packets_in_system > 0:
            self.current_packets_in_system -= 1

        self.accumulated_shortage_cost += self.shortage_cost_penalty

    def record_packet_blocked(self, now: float) -> None:
        """
        Registra un paquete rechazado por la política de control de flujo (s, Q):
        el nodo mantiene cerrado su canal de entrada porque agotó el lote Q vigente.
        También es tráfico perdido, por lo que acumula penalización de ruptura.
        """
        self.update_integrals(now)
        self.total_blocked += 1
        if self.current_packets_in_system > 0:
            self.current_packets_in_system -= 1

        self.accumulated_shortage_cost += self.shortage_cost_penalty

    def update_integrals(self, now: float) -> None:
        """
        Actualiza el cálculo integral de área bajo la curva para L y Lq:
        Area_Lq += N_q * Delta_t
        Area_L  += N_sys * Delta_t
        Holding_Cost += N_q * H * Delta_t
        """
        dt = max(0.0, now - self.last_update_time)
        if dt > 0.0:
            self.integral_area_lq += self.current_packets_in_queue * dt
            self.integral_area_l += self.current_packets_in_system * dt
            self.accumulated_holding_cost += (
                self.current_packets_in_queue * self.holding_cost_rate * dt
            )
            self.last_update_time = now

    def get_metrics_snapshot(self, current_time: float) -> Dict[str, Any]:
        """
        Calcula y retorna una instantánea completa de las métricas para HUD y reporte.
        """
        # Asegurar actualización al instante solicitado
        self.update_integrals(current_time)

        t = max(0.001, current_time)

        # Promedios ponderados en el tiempo
        l_q = self.integral_area_lq / t
        l = self.integral_area_l / t

        # Tiempos medios por paquete completado
        if self.total_processed > 0:
            w_q = self.sum_queue_wait_time / self.total_processed
            w = self.sum_system_time / self.total_processed
        else:
            w_q = 0.0
            w = 0.0

        # Tasa de pérdida porcentual sobre el total de tráfico ofrecido.
        # Incluye ambas causas de pérdida: desbordamiento y bloqueo por control de flujo.
        total_lost = self.total_dropped + self.total_blocked + self.total_link_failures
        total_offered = self.total_generated
        if total_offered > 0:
            loss_rate_pct = (total_lost / total_offered) * 100.0
            overflow_rate_pct = (self.total_dropped / total_offered) * 100.0
        else:
            loss_rate_pct = 0.0
            overflow_rate_pct = 0.0

        # Costos consolidados
        holding_cost = self.accumulated_holding_cost
        shortage_cost = self.accumulated_shortage_cost
        global_cost = holding_cost + shortage_cost

        return {
            "simulation_time": current_time,
            "total_generated": self.total_generated,
            "total_processed": self.total_processed,
            "total_dropped": self.total_dropped,
            "total_blocked": self.total_blocked,
            "total_link_failures": self.total_link_failures,
            "total_lost": total_lost,
            "total_misrouted": self.total_misrouted,
            "loss_rate_pct": loss_rate_pct,
            "overflow_rate_pct": overflow_rate_pct,
            "L_q": l_q,
            "L": l,
            "W_q": w_q,
            "W": w,
            "holding_cost": holding_cost,
            "shortage_cost": shortage_cost,
            "global_cost": global_cost,
            "current_queue": self.current_packets_in_queue,
            "current_system": self.current_packets_in_system,
        }
