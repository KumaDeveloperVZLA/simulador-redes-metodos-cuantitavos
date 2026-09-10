"""
Módulo de Asignación Óptima - Algoritmo Húngaro.
Optimiza el enrutamiento y balanceo de carga en intervalos discretos Delta t
utilizando scipy.optimize.linear_sum_assignment sobre una matriz dinámica de costos.
"""

from typing import List, Dict, Tuple, Any
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
    dummy_penalty: float = DUMMY_PENALTY_COST
) -> Tuple[List[Tuple[Packet, NetworkLink]], Dict[str, Any]]:
    """
    Resuelve la asignación 1 a 1 de paquetes pendientes a enlaces de transmisión
    minimizando el costo total global de tránsito y congestión:
    C_ij = Latencia_Actual_ij + alpha * (Buffer_Actual_j / S_j)

    Si N != M, balancea la matriz a cuadrada (K x K) con costos de penalización dummy.
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
        for j in range(m):
            link = candidate_links[j]
            if not link.is_active:
                # Enlace caído: penalización máxima
                balanced_cost_matrix[i, j] = dummy_penalty
                continue

            target_node = nodes_dict.get(link.target_id)
            saturation = target_node.saturation if target_node else 0.0

            # C_ij = Latencia + alpha * Saturación
            cost = link.current_latency + alpha * saturation
            balanced_cost_matrix[i, j] = cost

    # Ejecución del Algoritmo Húngaro (Kuhn-Munkres) vía SciPy
    row_indices, col_indices = linear_sum_assignment(balanced_cost_matrix)

    assignments: List[Tuple[Packet, NetworkLink]] = []
    total_assigned_cost = 0.0

    for r, c in zip(row_indices, col_indices):
        # Descartar filas o columnas ficticias (dummy) y enlaces caídos
        if r < n and c < m:
            link = candidate_links[c]
            if link.is_active and balanced_cost_matrix[r, c] < (dummy_penalty / 2.0):
                assignments.append((pending_packets[r], link))
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
