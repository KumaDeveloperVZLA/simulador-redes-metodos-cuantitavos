"""
Módulo de Asignación Óptima - Algoritmo Húngaro.
Optimiza el enrutamiento y balanceo de carga en intervalos discretos Delta t
utilizando scipy.optimize.linear_sum_assignment sobre una matriz dinámica de costos.
"""

from typing import List, Dict, Tuple, Any, Callable, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment

from ..models.packet import Packet
from ..models.node import RouterNode
from ..models.link import NetworkLink
from ..config import ALPHA_SATURATION_WEIGHT, DUMMY_PENALTY_COST


def solve_hungarian_assignment(
    pending_packets: List[Packet],
    candidate_links: List[NetworkLink],
    nodes_dict: Dict[str, RouterNode],
    alpha: float = ALPHA_SATURATION_WEIGHT,
    dummy_penalty: float = DUMMY_PENALTY_COST,
    feasible: Optional[Callable[[Packet, NetworkLink], bool]] = None
) -> Tuple[List[Tuple[Packet, NetworkLink]], Dict[str, Any]]:
    """
    Resuelve la asignación 1 a 1 de paquetes pendientes a enlaces de transmisión
    minimizando el costo total global de tránsito y congestión:
    C_ij = Latencia_Actual_ij + alpha * (Buffer_Actual_j / S_j)

    Si N != M, balancea la matriz a cuadrada (K x K) con costos de penalización dummy.

    `feasible(paquete, enlace)` permite al motor declarar qué pares son admisibles
    (enlace que sale del nodo donde espera el paquete, ruta válida hacia su destino,
    vecino con el canal de entrada abierto). Los pares no admisibles conservan la
    penalización dummy y son descartados del resultado. Un enlace caído queda
    excluido por su propia latencia de penalización (NetworkLink.current_latency).
    """
    if not pending_packets or not candidate_links:
        return [], {"status": "EMPTY", "assigned": 0, "total_cost": 0.0}

    n = len(pending_packets)
    m = len(candidate_links)
    k = max(n, m)

    # Matriz cuadrada balanceada con penalizaciones dummy
    balanced_cost_matrix = np.full((k, k), dummy_penalty, dtype=np.float64)

    # Construcción de la matriz C_ij
    for i in range(n):
        packet = pending_packets[i]
        for j in range(m):
            link = candidate_links[j]

            # Pares no admisibles: conservan el costo dummy de la matriz balanceada
            if feasible is not None and not feasible(packet, link):
                continue

            target_node = nodes_dict.get(link.target_id)
            saturation = target_node.saturation if target_node else 0.0

            # C_ij = Latencia + alpha * Saturación
            cost = link.current_latency + alpha * saturation
            balanced_cost_matrix[i, j] = min(cost, dummy_penalty)

    # Ejecución del Algoritmo Húngaro (Kuhn-Munkres) vía SciPy
    row_indices, col_indices = linear_sum_assignment(balanced_cost_matrix)

    assignments: List[Tuple[Packet, NetworkLink]] = []
    total_assigned_cost = 0.0

    for r, c in zip(row_indices, col_indices):
        # Descartar filas/columnas ficticias (dummy) y pares penalizados
        if r < n and c < m and balanced_cost_matrix[r, c] < (dummy_penalty / 2.0):
            assignments.append((pending_packets[r], candidate_links[c]))
            total_assigned_cost += balanced_cost_matrix[r, c]

    diag_info = {
        "status": "OPTIMAL",
        "packets_count": n,
        "links_count": m,
        "assigned_count": len(assignments),
        "total_cost": float(total_assigned_cost),
        "average_cost": float(total_assigned_cost / len(assignments)) if assignments else 0.0
    }

    return assignments, diag_info
