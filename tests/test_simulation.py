"""
Pruebas Unitarias y de Integración del Simulador de Redes.
Verifica modelos matemáticos de Teoría de Colas, Inventarios (s, Q),
Algoritmo Húngaro y generación de reportes.
"""

import unittest
import numpy as np
from scipy.optimize import linear_sum_assignment

from src.models.packet import Packet, PacketStatus
from src.models.node import RouterNode, AdmissionResult
from src.models.link import NetworkLink
from src.simulation.metrics import MetricsTracker
from src.simulation.hungarian import solve_hungarian_assignment
from src.reporting.exporter import format_simulation_report


class TestQueuingTheoryAndInventory(unittest.TestCase):

    def test_node_finite_capacity_and_overflow(self):
        """Verifica que el buffer respete la capacidad finita S y descarte por overflow."""
        # batch_Q amplio para aislar el desbordamiento del bloqueo por control de flujo
        node = RouterNode("R_TEST", "Router Test", (100, 100), capacity_S=3, threshold_s=1, batch_Q=50)

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
        self.assertIs(admitted_overflow, AdmissionResult.OVERFLOW)
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

    def test_flow_control_batch_Q_is_effective(self):
        """El lote Q debe consumirse realmente y cerrar el canal de entrada al agotarse."""
        node = RouterNode("R_Q", "Router Lote", (0, 0), capacity_S=50, threshold_s=2, batch_Q=4)

        # El nodo arranca con un lote Q autorizado
        self.assertEqual(node.remaining_batch_credits, 4)

        # Las 4 primeras admisiones consumen el lote; a partir de la 3ra la ocupación
        # supera s = 2, de modo que no se autoriza un lote nuevo.
        for i in range(4):
            self.assertTrue(node.enqueue_packet(Packet(i, "S", "D", 0.0), 0.0))
        self.assertEqual(node.remaining_batch_credits, 0)
        self.assertFalse(node.has_admission_credit())

        # Canal cerrado: el siguiente paquete se rechaza por control de flujo,
        # NO por desbordamiento (quedan 46 posiciones libres de las 50).
        blocked_pkt = Packet(99, "S", "D", 0.0)
        result = node.enqueue_packet(blocked_pkt, 0.0)
        self.assertFalse(result)
        self.assertIs(result, AdmissionResult.FLOW_CONTROL_BLOCKED)
        self.assertEqual(blocked_pkt.status, PacketStatus.BLOCKED)
        self.assertEqual(node.total_dropped, 0)
        self.assertEqual(node.total_flow_control_blocks, 1)

        # Al drenar el buffer hasta el umbral s se autoriza un lote Q nuevo
        batches_before = node.total_batches_granted
        node.dequeue_packet(1.0)
        node.dequeue_packet(1.0)
        self.assertEqual(node.occupancy, 2)
        self.assertTrue(node.flow_control_signal)
        self.assertEqual(node.total_batches_granted, batches_before + 1)
        self.assertEqual(node.remaining_batch_credits, 4)
        self.assertTrue(node.enqueue_packet(Packet(100, "S", "D", 1.0), 1.0))

    def test_wq_excludes_service_time(self):
        """Wq debe medirse hasta el INICIO del servicio, no hasta su finalización."""
        node = RouterNode("R_W", "Router Wq", (0, 0), capacity_S=10, threshold_s=5, batch_Q=10)
        pkt = Packet(1, "S", "D", 0.0)

        node.enqueue_packet(pkt, 0.0)
        # El paquete espera 0.2 s en cola y luego entra a servicio
        served = node.dequeue_packet(0.2)
        self.assertIs(served, pkt)
        self.assertAlmostEqual(pkt.total_queue_wait_time, 0.2, places=6)
        self.assertEqual(pkt.status, PacketStatus.IN_SERVICE)

        # El tiempo de servicio se acumula aparte y no contamina Wq
        pkt.add_service_time(0.5)
        self.assertAlmostEqual(pkt.total_queue_wait_time, 0.2, places=6)
        self.assertAlmostEqual(pkt.total_service_time, 0.5, places=6)

    def test_metrics_blocked_packets_are_accounted(self):
        """Los rechazos por control de flujo son pérdida y penalizan, pero no son overflow."""
        tracker = MetricsTracker(holding_cost_rate=0.05, shortage_cost_penalty=10.0)
        tracker.record_packet_generation(0.0)
        tracker.record_packet_generation(0.0)
        tracker.record_packet_dropped(1.0)
        tracker.record_packet_blocked(1.0)

        snap = tracker.get_metrics_snapshot(1.0)
        self.assertEqual(snap["total_dropped"], 1)
        self.assertEqual(snap["total_blocked"], 1)
        self.assertEqual(snap["total_lost"], 2)
        self.assertAlmostEqual(snap["loss_rate_pct"], 100.0, places=2)
        self.assertAlmostEqual(snap["overflow_rate_pct"], 50.0, places=2)
        self.assertAlmostEqual(snap["shortage_cost"], 20.0, places=2)

        # La pérdida en tránsito por caída de enlace no debe contaminar el Overflow
        tracker.record_packet_generation(1.0)
        tracker.record_packet_lost_in_transit(1.0)
        snap2 = tracker.get_metrics_snapshot(1.0)
        self.assertEqual(snap2["total_dropped"], 1)
        self.assertEqual(snap2["total_link_failures"], 1)
        self.assertEqual(snap2["total_lost"], 3)
        self.assertAlmostEqual(snap2["shortage_cost"], 30.0, places=2)

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

    def test_hungarian_respects_feasibility_mask(self):
        """Los pares no admisibles quedan penalizados y fuera de la solución óptima."""
        p1 = Packet(1, "IN", "OUT", 0.0)
        n1 = RouterNode("T1", "Target 1", (200, 100), capacity_S=50)
        n2 = RouterNode("T2", "Target 2", (200, 200), capacity_S=50)
        l1 = NetworkLink("L1", "IN", "T1", base_latency=0.01)
        l2 = NetworkLink("L2", "IN", "T2", base_latency=0.05)

        # Solo L2 es admisible: aunque L1 es más barato, no debe asignarse
        assignments, diag = solve_hungarian_assignment(
            [p1], [l1, l2], {"T1": n1, "T2": n2}, alpha=5.0,
            feasible=lambda pkt, link: link.link_id == "L2"
        )
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0][1].link_id, "L2")
        self.assertEqual(diag["assigned_count"], 1)

    def test_destination_aware_routing_and_lambda_profile(self):
        """El motor enruta según el destino y reporta el lambda que rigió la corrida."""
        from src.simulation.bridge import SimulationBridge
        from src.simulation.engine import NetworkSimulationEngine

        bridge = SimulationBridge(initial_lambda=10.0, initial_mu=18.0)
        engine = NetworkSimulationEngine(bridge=bridge, initial_lambda=10.0, initial_mu=18.0)

        # Desde el ingreso Alpha, ambos destinos de salida son alcanzables
        self.assertIn("R_OUT_1", engine.reachable_from["R_IN_1"])
        self.assertIn("R_OUT_2", engine.reachable_from["R_IN_1"])

        # Un paquete destinado a R_OUT_1 encolado en Core Sur no tiene ruta:
        # R_CORE_3 solo alcanza R_OUT_2, de modo que no hay enlace hacia el destino.
        pkt = Packet(1, "R_IN_2", "R_OUT_1", 0.0)
        pkt.current_node_id = "R_CORE_3"
        self.assertEqual(engine._links_towards_destination(engine.nodes["R_CORE_3"], pkt), [])

        # Desde Core Centro, un paquete a R_OUT_1 solo puede salir por L6
        pkt2 = Packet(2, "R_IN_1", "R_OUT_1", 0.0)
        pkt2.current_node_id = "R_CORE_2"
        viable = [l.link_id for l in engine._links_towards_destination(engine.nodes["R_CORE_2"], pkt2)]
        self.assertIn("L6", viable)
        self.assertNotIn("L7", viable)

        # Perfil de lambda: media ponderada en el tiempo, no el último valor tecleado
        engine.current_lambda = 10.0
        engine._accumulate_parameter_profile(1.0)
        engine.current_lambda = 30.0
        engine._accumulate_parameter_profile(1.0)
        profile = engine.get_parameter_profile()
        self.assertAlmostEqual(profile["lambda_mean"], 20.0, places=6)
        self.assertEqual(profile["lambda_final"], 30.0)
        self.assertEqual(profile["lambda_initial"], 10.0)
        self.assertTrue(profile["lambda_varied"])

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

    def test_report_uses_time_weighted_lambda_and_reports_range(self):
        """El reporte publica el lambda medio ponderado y deja constancia del rango."""
        metrics = {
            "total_processed": 100,
            "total_dropped": 2,
            "total_blocked": 5,
            "loss_rate_pct": 6.5,
            "W_q": 0.04,
            "W": 0.10,
            "L": 4.5,
            "L_q": 1.2,
            "holding_cost": 25.50,
            "shortage_cost": 70.00,
            "global_cost": 95.50,
            "flow_control": {"flow_control_signals": 12, "batches_granted": 12},
        }
        profile = {
            "lambda_mean": 21.4,
            "lambda_initial": 15.0,
            "lambda_final": 5.0,
            "lambda_min": 5.0,
            "lambda_max": 40.0,
            "lambda_varied": True,
        }
        rep = format_simulation_report(
            sim_time=117.3,
            lambda_val=profile["lambda_mean"],
            mu_val=18.0,
            capacity_S=50,
            threshold_s=10,
            metrics=metrics,
            batch_Q=15,
            lambda_profile=profile
        )

        self.assertIn("Tasa de Llegada (lambda): 21.4 paquetes/s", rep)
        self.assertIn("inicial 15.0 -> final 5.0 paquetes/s", rep)
        self.assertIn("rango [5.0, 40.0]", rep)
        self.assertIn("Lote de Reabastecimiento (Q): 15 paquetes", rep)
        self.assertIn("Paquetes Bloqueados por Control de Flujo: 5", rep)
        self.assertIn("Señales de Control de Flujo (s, Q) emitidas: 12", rep)


if __name__ == "__main__":
    unittest.main()
