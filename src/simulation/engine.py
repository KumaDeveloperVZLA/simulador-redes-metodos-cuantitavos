"""
Motor de Simulación de Redes de Eventos Discretos con SimPy.
Integra el generador estocástico de Poisson, colas con atención exponencial (M/M/1/K),
asignación dinámica de enlaces mediante el Algoritmo Húngaro y control de inventario (s, Q).
"""

import time
import random
import threading
from typing import Dict, List, Optional, Any

import simpy

from ..config import (
    TOPOLOGY_NODES,
    TOPOLOGY_LINKS,
    DEFAULT_LAMBDA,
    DEFAULT_MU,
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q,
    HUNGARIAN_INTERVAL,
    ALPHA_SATURATION_WEIGHT
)
from ..models.packet import Packet, PacketStatus
from ..models.node import RouterNode
from ..models.link import NetworkLink
from .metrics import MetricsTracker
from .hungarian import solve_hungarian_assignment
from .bridge import SimulationBridge


class NetworkSimulationEngine:
    """
    Ejecuta el entorno SimPy en un hilo dedicado para garantizar que la GUI
    no se bloquee, calculando métricas continuas y sincronizando animaciones.
    """

    def __init__(
        self,
        bridge: SimulationBridge,
        initial_lambda: float = DEFAULT_LAMBDA,
        initial_mu: float = DEFAULT_MU
    ):
        self.bridge: SimulationBridge = bridge
        self.current_lambda: float = initial_lambda
        self.current_mu: float = initial_mu

        # Entorno SimPy
        self.env: simpy.Environment = simpy.Environment()

        # Diccionarios de topología
        self.nodes: Dict[str, RouterNode] = {}
        self.links: Dict[str, NetworkLink] = {}
        self.links_by_source: Dict[str, List[NetworkLink]] = {}

        # Métricas
        self.metrics: MetricsTracker = MetricsTracker()

        # Colección de paquetes activos en el sistema
        self.packet_counter: int = 0
        self.active_packets: Dict[int, Packet] = {}
        self._packets_lock = threading.Lock()

        # Hilo de ejecución
        self.worker_thread: Optional[threading.Thread] = None
        self._is_running: bool = False

        # Configurar topología y recursos SimPy
        self._setup_network()

    def _setup_network(self) -> None:
        """Inicializa nodos, enlaces y recursos SimPy según la configuración."""
        for n_data in TOPOLOGY_NODES:
            node = RouterNode(
                node_id=n_data["id"],
                name=n_data["name"],
                pos=n_data["pos"],
                capacity_S=n_data.get("capacity", DEFAULT_BUFFER_CAPACITY_S),
                threshold_s=n_data.get("threshold", DEFAULT_REORDER_POINT_S),
                batch_Q=n_data.get("batch", DEFAULT_ORDER_BATCH_Q),
                is_ingress=n_data.get("is_ingress", False),
                is_egress=n_data.get("is_egress", False)
            )
            # Servidor SimPy con capacidad 1 (M/M/1/K)
            node.server_resource = simpy.Resource(self.env, capacity=1)
            self.nodes[node.node_id] = node
            self.links_by_source[node.node_id] = []

        for l_data in TOPOLOGY_LINKS:
            link = NetworkLink(
                link_id=l_data["id"],
                source_id=l_data["source"],
                target_id=l_data["target"],
                base_latency=l_data["base_latency"]
            )
            self.links[link.link_id] = link
            if link.source_id in self.links_by_source:
                self.links_by_source[link.source_id].append(link)

    def start(self) -> None:
        """Inicia los procesos SimPy y el hilo de ejecución worker."""
        self._is_running = True

        # Lanzar procesos SimPy
        self.env.process(self._traffic_generator_process())
        self.env.process(self._hungarian_routing_process())

        # Iniciar procesos servidores de cada router
        for node in self.nodes.values():
            if not node.is_egress:
                self.env.process(self._router_service_process(node))

        # Arrancar hilo de fondo
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()

    def _traffic_generator_process(self):
        """
        Generador estocástico de tráfico según un Proceso de Poisson.
        Intervalos entre llegadas: random.expovariate(lambda).
        """
        ingress_nodes = [n for n in self.nodes.values() if n.is_ingress]
        egress_nodes = [n for n in self.nodes.values() if n.is_egress]

        while self._is_running:
            # Intervalo exponencial con la tasa actual de llegada lambda
            lambd = max(0.5, self.current_lambda)
            inter_arrival = random.expovariate(lambd)
            yield self.env.timeout(inter_arrival)

            # Generar paquete
            self.packet_counter += 1
            src_node = random.choice(ingress_nodes)
            dst_node = random.choice(egress_nodes)

            packet = Packet(
                packet_id=self.packet_counter,
                source_id=src_node.node_id,
                destination_id=dst_node.node_id,
                creation_time=self.env.now
            )

            with self._packets_lock:
                self.active_packets[packet.packet_id] = packet

            # Registrar creación en el monitor de métricas
            self.metrics.record_packet_generation(self.env.now)

            # Encolar en el buffer del router de ingreso con capacidad finita S
            admitted = src_node.enqueue_packet(packet, self.env.now)
            if admitted:
                self.metrics.record_packet_enqueue(self.env.now)
            else:
                # Buffer Overflow en nodo de ingreso
                self.metrics.record_packet_dropped(self.env.now)
                with self._packets_lock:
                    self.active_packets.pop(packet.packet_id, None)

    def _hungarian_routing_process(self):
        """
        Proceso periódico que ejecuta el Algoritmo Húngaro cada Delta t (HUNGARIAN_INTERVAL)
        para optimizar la asignación de flujos de paquetes pendientes a enlaces disponibles.
        """
        while self._is_running:
            yield self.env.timeout(HUNGARIAN_INTERVAL)

            # Recolectar paquetes en espera en nodos de ingreso e intermedios
            for src_id, outgoing_links in self.links_by_source.items():
                node = self.nodes[src_id]
                if node.is_egress or not node.buffer:
                    continue

                active_links = [lnk for lnk in outgoing_links if lnk.is_active]
                if not active_links:
                    continue

                # Paquetes pendientes en este nodo (hasta el número de enlaces disponibles)
                pending_pkts = list(node.buffer)[:len(active_links) * 2]
                if not pending_pkts:
                    continue

                # Resolver asignación óptima vía Algoritmo Húngaro
                assignments, _ = solve_hungarian_assignment(
                    pending_packets=pending_pkts,
                    candidate_links=active_links,
                    nodes_dict=self.nodes,
                    alpha=ALPHA_SATURATION_WEIGHT
                )

                # Priorizar enrutamiento según los enlaces óptimos encontrados
                for pkt, chosen_link in assignments:
                    pkt.current_link_id = chosen_link.link_id

    def _router_service_process(self, node: RouterNode):
        """
        Proceso de atención de paquetes en cada router.
        Distribución exponencial de tasa mu para el tiempo de procesamiento/servicio.
        """
        while self._is_running:
            # Esperar a que haya paquetes en cola
            if not node.buffer:
                yield self.env.timeout(0.01)
                continue

            with node.server_resource.request() as req:
                yield req

                if not node.buffer:
                    continue

                packet = node.buffer[0]

                # Determinar enlace de reenvío
                candidate_links = self.links_by_source.get(node.node_id, [])
                active_links = [l for l in candidate_links if l.is_active]

                if not active_links:
                    # Todos los enlaces caídos: retener en buffer
                    yield self.env.timeout(0.05)
                    continue

                # Seleccionar enlace asignado por el Húngaro o por menor costo dinámico
                chosen_link = None
                if packet.current_link_id and packet.current_link_id in self.links:
                    assigned_link = self.links[packet.current_link_id]
                    if assigned_link.is_active and assigned_link.source_id == node.node_id:
                        chosen_link = assigned_link

                if not chosen_link:
                    # Enlace de menor costo: latencia + alpha * saturación
                    chosen_link = min(
                        active_links,
                        key=lambda lnk: lnk.current_latency + ALPHA_SATURATION_WEIGHT * self.nodes[lnk.target_id].saturation
                    )

                # Tiempo de servicio exponencial con tasa mu
                mu = max(1.0, self.current_mu)
                service_duration = random.expovariate(mu)
                yield self.env.timeout(service_duration)

                # Extraer del buffer tras el servicio
                node.dequeue_packet(self.env.now)
                self.metrics.record_packet_dequeue(self.env.now)

                # Transmitir a través del enlace elegido
                self.env.process(self._packet_transmission_process(packet, chosen_link))

    def _packet_transmission_process(self, packet: Packet, link: NetworkLink):
        """
        Simula el desplazamiento del paquete por un enlace de red
        y su entrega en el nodo receptor.
        """
        src_node = self.nodes[link.source_id]
        tgt_node = self.nodes[link.target_id]

        transit_time = link.current_latency
        link.packets_in_transit.append(packet)

        # Iniciar animación visual interpolada (LERP)
        packet.start_transit(
            now=self.env.now,
            link_id=link.link_id,
            duration=transit_time,
            start_pos=src_node.pos,
            end_pos=tgt_node.pos
        )

        yield self.env.timeout(transit_time)

        # Tránsito finalizado
        if packet in link.packets_in_transit:
            link.packets_in_transit.remove(packet)
        link.total_transmitted += 1

        # Si el enlace se cayó en pleno tránsito, el paquete se pierde
        if not link.is_active:
            self.metrics.record_packet_dropped(self.env.now)
            with self._packets_lock:
                self.active_packets.pop(packet.packet_id, None)
            return

        # Si llegó al nodo de destino final (Egress)
        if tgt_node.is_egress:
            packet.mark_completed(self.env.now)
            self.metrics.record_packet_completed(
                now=self.env.now,
                total_wait_time=packet.total_queue_wait_time,
                total_system_time=packet.total_system_time
            )
            with self._packets_lock:
                self.active_packets.pop(packet.packet_id, None)
        else:
            # Encolar en el siguiente nodo intermedio
            admitted = tgt_node.enqueue_packet(packet, self.env.now)
            if admitted:
                self.metrics.record_packet_enqueue(self.env.now)
            else:
                self.metrics.record_packet_dropped(self.env.now)
                with self._packets_lock:
                    self.active_packets.pop(packet.packet_id, None)

    def _run_loop(self) -> None:
        """
        Loop continuo del worker thread:
        Sincroniza el tiempo discreto de SimPy con el tiempo real de pared
        y publica snapshots hacia el puente thread-safe.
        """
        last_wall_time = time.time()
        sim_step = 0.01

        while self._is_running:
            now_wall = time.time()
            dt_wall = now_wall - last_wall_time
            last_wall_time = now_wall

            # Procesar comandos de la GUI
            commands = self.bridge.poll_commands()
            for cmd in commands:
                action = cmd.get("action")
                if action == "SET_LAMBDA":
                    self.current_lambda = float(cmd["value"])
                elif action == "SET_MU":
                    self.current_mu = float(cmd["value"])
                elif action == "TOGGLE_LINK":
                    lnk_id = cmd["link_id"]
                    if lnk_id in self.links:
                        self.links[lnk_id].toggle_state()
                elif action == "STOP":
                    self._is_running = False
                    break

            if not self._is_running:
                break

            # Si la simulación está pausada, dormir brevemente
            if self.bridge.is_paused:
                time.sleep(0.02)
                continue

            # Avanzar SimPy un paso proporcional al delta de tiempo real
            target_time = self.env.now + min(0.1, max(sim_step, dt_wall))
            try:
                self.env.run(until=target_time)
            except Exception as ex:
                pass

            # Construir snapshot para la GUI
            self._publish_current_state()

            # Evitar uso excesivo de CPU manteniendo tasa estable
            time.sleep(0.008)

    def _publish_current_state(self) -> None:
        """Genera y envía el snapshot de renderizado a la GUI."""
        sim_now = self.env.now
        metrics_snap = self.metrics.get_metrics_snapshot(sim_now)

        # Snapshot de nodos
        nodes_state = []
        for n in self.nodes.values():
            nodes_state.append({
                "id": n.node_id,
                "name": n.name,
                "pos": n.pos,
                "occupancy": n.occupancy,
                "capacity": n.capacity_S,
                "saturation": n.saturation,
                "color": n.get_color_category(),
                "flow_control": n.flow_control_signal,
                "is_ingress": n.is_ingress,
                "is_egress": n.is_egress
            })

        # Snapshot de enlaces
        links_state = []
        for l in self.links.values():
            src_pos = self.nodes[l.source_id].pos
            tgt_pos = self.nodes[l.target_id].pos
            links_state.append({
                "id": l.link_id,
                "source_id": l.source_id,
                "target_id": l.target_id,
                "is_active": l.is_active,
                "current_latency": l.current_latency,
                "in_transit_count": len(l.packets_in_transit),
                "src_pos": src_pos,
                "tgt_pos": tgt_pos,
                "color": l.get_color()
            })

        # Snapshot de paquetes en animación visual
        packets_state = []
        with self._packets_lock:
            for p in self.active_packets.values():
                if p.status == PacketStatus.IN_TRANSIT:
                    p.update_visual_progress(sim_now)
                    x, y = p.get_current_coords()
                    packets_state.append({
                        "id": p.packet_id,
                        "pos": (x, y),
                        "progress": p.visual_progress,
                        "link_id": p.current_link_id
                    })

        snapshot = {
            "sim_time": sim_now,
            "lambda": self.current_lambda,
            "mu": self.current_mu,
            "metrics": metrics_snap,
            "nodes": nodes_state,
            "links": links_state,
            "packets": packets_state
        }

        self.bridge.publish_snapshot(snapshot)

    def stop(self) -> Dict[str, Any]:
        """Detiene la simulación y retorna las métricas finales."""
        self._is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        return self.metrics.get_metrics_snapshot(self.env.now)
