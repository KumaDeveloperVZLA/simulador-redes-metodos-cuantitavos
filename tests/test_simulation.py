"""
Pruebas Unitarias y de Integración del Simulador de Redes.
Verifica modelos matemáticos de Teoría de Colas, Inventarios (s, Q),
Algoritmo Húngaro y generación de reportes.
"""

import unittest
import numpy as np
from scipy.optimize import linear_sum_assignment

from src.models.packet import Packet, PacketStatus
from src.models.node import RouterNode
from src.models.link import NetworkLink
from src.simulation.metrics import MetricsTracker
from src.simulation.hungarian import solve_hungarian_assignment
from src.reporting.exporter import format_simulation_report


class TestQueuingTheoryAndInventory(unittest.TestCase):

    def test_node_finite_capacity_and_overflow(self):
        """Verifica que el buffer respete la capacidad finita S y descarte por overflow."""
        node = RouterNode("R_TEST", "Router Test", (100, 100), capacity_S=3, threshold_s=1, batch_Q=2)

        # Encolar 3 paquetes (deben ser admitidos)
        for i in range(3):
            pkt = Packet(i, "SRC", "DST", 0.0)
            admitted = node.enqueue_packet(pkt, 0.1 * i)
            self.assertTrue(admitted)
            self.assertEqual(pkt.status, PacketStatus.QUEUED)

        self.assertEqual(node.occupancy, 3)
        self.assertEqual(node.saturation, 1.0)
        self.assertEqual(node.total_dropped, 0)

        # Encolar 4to paquete (debe ser descartado por buffer overflow / ruptura)
        pkt_overflow = Packet(99, "SRC", "DST", 0.5)
        admitted_overflow = node.enqueue_packet(pkt_overflow, 0.5)
        self.assertFalse(admitted_overflow)
        self.assertEqual(pkt_overflow.status, PacketStatus.DROPPED)
        self.assertEqual(node.total_dropped, 1)

    def test_flow_control_s_Q_policy(self):
        """Verifica la activación de la señal de reabastecimiento / control de flujo (s, Q)."""
        node = RouterNode("R_INV", "Router Inv", (100, 100), capacity_S=10, threshold_s=3, batch_Q=5)

        # Inicialmente vacío: ocupación 0 <= s=3 -> señal activa
        self.assertTrue(node.check_flow_control())
        self.assertTrue(node.flow_control_signal)

        # Llenar con 5 paquetes (> s=3)
        for i in range(5):
            node.enqueue_packet(Packet(i, "S", "D", 0.0), 0.0)

        self.assertFalse(node.check_flow_control())
        self.assertFalse(node.flow_control_signal)

        # Desencolar hasta que queden 2 paquetes (<= s=3)
        node.dequeue_packet(1.0)
        node.dequeue_packet(1.0)
        node.dequeue_packet(1.0)
        self.assertEqual(node.occupancy, 2)
        self.assertTrue(node.flow_control_signal)

    def test_metrics_tracker_integral_and_costs(self):
        """Verifica el cálculo integral de L, Lq, holding costs y penalizaciones."""
        tracker = MetricsTracker(holding_cost_rate=0.05, shortage_cost_penalty=10.0)

        # t=0: Llegan 2 paquetes
        tracker.record_packet_generation(0.0)
        tracker.record_packet_enqueue(0.0)
        tracker.record_packet_generation(0.0)
        tracker.record_packet_enqueue(0.0)

        # Avanzar hasta t=10 sin cambios (2 paquetes en cola durante 10s -> Area Lq = 20)
        tracker.update_integrals(10.0)
        snap = tracker.get_metrics_snapshot(10.0)

        self.assertAlmostEqual(snap["L_q"], 2.0, places=2)
        # Holding cost = 2 pkts * 0.05 $/pkt*s * 10 s = 1.0 $
        self.assertAlmostEqual(snap["holding_cost"], 1.0, places=2)

        # Registrar un descarte (ruptura)
        tracker.record_packet_dropped(10.0)
        snap2 = tracker.get_metrics_snapshot(10.0)
        self.assertEqual(snap2["total_dropped"], 1)
        self.assertAlmostEqual(snap2["shortage_cost"], 10.0, places=2)
        self.assertAlmostEqual(snap2["global_cost"], 11.0, places=2)

    def test_hungarian_assignment_optimization(self):
        """Verifica la asignación 1 a 1 óptima y balanceo de matriz rectangular con SciPy."""
        # 2 paquetes pendientes
        p1 = Packet(1, "IN", "OUT", 0.0)
        p2 = Packet(2, "IN", "OUT", 0.0)
        pending = [p1, p2]

        # Nodos destino
        n1 = RouterNode("T1", "Target 1", (200, 100), capacity_S=50)
        n2 = RouterNode("T2", "Target 2", (200, 200), capacity_S=50)
        # Saturar T1 con 40/50 = 80%, T2 con 0/50 = 0%
        for i in range(40):
            n1.enqueue_packet(Packet(100 + i, "S", "D", 0.0), 0.0)

        nodes_dict = {"T1": n1, "T2": n2}

        # Enlaces: L1 a T1 (baja latencia base 0.02s pero alta saturación de nodo)
        # Enlace: L2 a T2 (latencia base 0.05s pero nodo completamente libre)
        l1 = NetworkLink("L1", "IN", "T1", base_latency=0.02)
        l2 = NetworkLink("L2", "IN", "T2", base_latency=0.05)
        links = [l1, l2]

        # Con alpha=5.0:
        # C_11 = 0.02 + 5.0 * (40/50) = 0.02 + 4.0 = 4.02
        # C_12 = 0.05 + 5.0 * (0/50)  = 0.05
        # El algoritmo asignará uno a L2 (el más económico) y el otro a L1
        assignments, diag = solve_hungarian_assignment(pending, links, nodes_dict, alpha=5.0)

        self.assertEqual(len(assignments), 2)
        self.assertEqual(diag["status"], "OPTIMAL")

    def test_report_template_format(self):
        """Verifica que el reporte generado respete fielmente la estructura exigida."""
        metrics = {
            "total_processed": 100,
            "total_dropped": 2,
            "loss_rate_pct": 2.0,
            "W_q": 0.15,
            "L": 4.5,
            "holding_cost": 25.50,
            "shortage_cost": 20.00,
            "global_cost": 45.50
        }
        rep = format_simulation_report(
            sim_time=60.0,
            lambda_val=15.0,
            mu_val=18.0,
            capacity_S=50,
            threshold_s=10,
            metrics=metrics
        )

        self.assertIn("REPORTE DE SIMULACIÓN DE RED", rep)
        self.assertIn("Tiempo Total de Simulación: 60.0 s", rep)
        self.assertIn("Tasa de Llegada (lambda): 15.0 paquetes/s", rep)
        self.assertIn("Tasa de Servicio (mu): 18.0 paquetes/s", rep)
        self.assertIn("Capacidad de Buffer (S): 50 paquetes", rep)
        self.assertIn("Umbral Reabastecimiento (s): 10 paquetes", rep)
        self.assertIn("Paquetes Procesados: 100", rep)
        self.assertIn("Paquetes Perdidos (Overflow): 2", rep)
        self.assertIn("Tasa de Pérdida: 2.00%", rep)
        self.assertIn("Tiempo Medio en Cola (Wq): 0.15 s", rep)
        self.assertIn("Promedio Paquetes en Sistema (L): 4.50", rep)
        self.assertIn("Costo Total de Almacenamiento: $25.50", rep)
        self.assertIn("Costo Total de Penalización (Ruptura): $20.00", rep)
        self.assertIn("Costo Global del Sistema: $45.50", rep)


if __name__ == "__main__":
    unittest.main()
