"""
Motor de Simulación de Redes de Eventos Discretos con SimPy.
Integra el generador estocástico de Poisson, colas con atención exponencial (M/M/1/K),
asignación dinámica de enlaces mediante el Algoritmo Húngaro y control de inventario (s, Q).
"""

import time
import random
import threading
import traceback
from typing import Dict, List, Optional, Any, Set, Tuple

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
    ALPHA_SATURATION_WEIGHT,
    BACKPRESSURE_RETRY_DELAY
)
from ..models.packet import Packet, PacketStatus
from ..models.node import RouterNode, AdmissionResult
from ..models.link import NetworkLink
from .metrics import MetricsTracker
from .hungarian import solve_hungarian_assignment
from .bridge import SimulationBridge

# Número máximo de excepciones consecutivas del entorno SimPy antes de abortar
MAX_ENGINE_ERRORS = 5


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
        self.initial_lambda: float = initial_lambda
        self.initial_mu: float = initial_mu

        # Entorno SimPy
        self.env: simpy.Environment = simpy.Environment()

        # Diccionarios de topología
        self.nodes: Dict[str, RouterNode] = {}
        self.links: Dict[str, NetworkLink] = {}
        self.links_by_source: Dict[str, List[NetworkLink]] = {}

        # Tabla de alcanzabilidad: nodos a los que se puede llegar desde cada nodo
        # siguiendo únicamente enlaces operativos (se recalcula ante cada falla).
        self.reachable_from: Dict[str, Set[str]] = {}

        # Métricas
        self.metrics: MetricsTracker = MetricsTracker()

        # Perfil temporal de los parámetros lambda y mu (pueden cambiarse en caliente
        # desde la GUI: el reporte debe informar el valor que realmente rigió la corrida).
        self._lambda_time_integral: float = 0.0
        self._mu_time_integral: float = 0.0
        self._parameter_elapsed: float = 0.0
        self._lambda_min: float = initial_lambda
        self._lambda_max: float = initial_lambda
        self._mu_min: float = initial_mu
        self._mu_max: float = initial_mu

        # Colección de paquetes activos en el sistema
        self.packet_counter: int = 0
        self.active_packets: Dict[int, Packet] = {}
        self._packets_lock = threading.Lock()

        # Diagnóstico del Algoritmo Húngaro y del propio motor
        self.last_assignment_info: Dict[str, Any] = {"status": "IDLE", "assigned_count": 0}
        self.engine_errors: int = 0
        self.last_engine_error: Optional[str] = None

        # Hilo de ejecución
        self.worker_thread: Optional[threading.Thread] = None
        self._is_running: bool = False

        # Configurar topología y recursos SimPy
        self._setup_network()
        self._rebuild_reachability()

    @property
    def is_running(self) -> bool:
        """Indica si el motor sigue vivo (se apaga solo ante fallos repetidos)."""
        return self._is_running

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

    # ========================================================
    # Enrutamiento orientado al destino del paquete
    # ========================================================

    def _rebuild_reachability(self) -> None:
        """
        Recalcula, para cada nodo, el conjunto de nodos alcanzables siguiendo
        enlaces operativos. Se invoca al arrancar y cada vez que un enlace cambia
        de estado, de modo que el enrutamiento no proponga rutas rotas.
        """
        for node_id in self.nodes:
            reachable: Set[str] = set()
            stack = [node_id]
            while stack:
                current = stack.pop()
                for link in self.links_by_source.get(current, []):
                    if not link.is_active:
                        continue
                    if link.target_id not in reachable:
                        reachable.add(link.target_id)
                        stack.append(link.target_id)
            self.reachable_from[node_id] = reachable

    def _links_towards_destination(self, node: RouterNode, packet: Packet) -> List[NetworkLink]:
        """
        Enlaces operativos que salen de `node` y por los que el destino del paquete
        sigue siendo alcanzable. Es lo que hace que Packet.destination_id gobierne
        realmente la ruta en lugar de ser un atributo decorativo.
        """
        destination = packet.destination_id
        viable: List[NetworkLink] = []
        for link in self.links_by_source.get(node.node_id, []):
            if not link.is_active:
                continue
            if link.target_id == destination or destination in self.reachable_from.get(link.target_id, set()):
                viable.append(link)
        return viable

    def _downstream_accepts(self, link: NetworkLink) -> bool:
        """
        Control de flujo (s, Q) aguas abajo: un vecino solo recibe tráfico si tiene
        buffer libre y saldo del lote Q que autorizó. Los nodos de salida (egress)
        son sumideros y siempre aceptan.
        """
        target = self.nodes.get(link.target_id)
        if target is None:
            return False
        if target.is_egress:
            return True
        return target.occupancy < target.capacity_S and target.has_admission_credit()

    def _link_cost(self, link: NetworkLink) -> float:
        """Costo dinámico C_ij = Latencia actual + alpha * Saturación del nodo destino."""
        target = self.nodes.get(link.target_id)
        saturation = target.saturation if target else 0.0
        return link.current_latency + ALPHA_SATURATION_WEIGHT * saturation

    def _is_feasible_pair(self, packet: Packet, link: NetworkLink) -> bool:
        """Predicado de admisibilidad paquete-enlace usado por el Algoritmo Húngaro."""
        if not link.is_active or link.source_id != packet.current_node_id:
            return False
        destination = packet.destination_id
        if link.target_id != destination and destination not in self.reachable_from.get(link.target_id, set()):
            return False
        return self._downstream_accepts(link)

    def _select_output_link(self, node: RouterNode, packet: Packet) -> Optional[NetworkLink]:
        """
        Elige el enlace de salida al terminar el servicio, en este orden:
          1. Enlaces que conducen al destino del paquete (si no hay ninguno, se admite
             cualquier enlace operativo como desvío de emergencia y la entrega se
             contabiliza como reencaminada).
          2. Se descartan los vecinos con el canal de entrada cerrado por (s, Q).
          3. Si el Algoritmo Húngaro dejó una asignación aún vigente, se respeta.
          4. En su defecto, enlace de menor costo dinámico latencia + alpha * saturación.
        """
        routed = self._links_towards_destination(node, packet)
        if not routed:
            routed = [lnk for lnk in self.links_by_source.get(node.node_id, []) if lnk.is_active]
        if not routed:
            return None

        available = [lnk for lnk in routed if self._downstream_accepts(lnk)]
        if not available:
            return None

        # Asignación del Húngaro, válida solo dentro de su ventana Delta t
        if packet.assigned_link_id and self.env.now <= packet.assignment_expiry:
            for lnk in available:
                if lnk.link_id == packet.assigned_link_id:
                    return lnk

        return min(available, key=self._link_cost)

    # ========================================================
    # Procesos SimPy
    # ========================================================

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
            result = src_node.enqueue_packet(packet, self.env.now)
            self._record_admission(packet, result)

    def _record_admission(self, packet: Packet, result: AdmissionResult) -> None:
        """Contabiliza el resultado de un intento de admisión en un buffer."""
        if result is AdmissionResult.ADMITTED:
            self.metrics.record_packet_enqueue(self.env.now)
            return

        if result is AdmissionResult.OVERFLOW:
            self.metrics.record_packet_dropped(self.env.now)
        else:
            # Rechazado por la política de control de flujo (s, Q)
            self.metrics.record_packet_blocked(self.env.now)

        with self._packets_lock:
            self.active_packets.pop(packet.packet_id, None)

    def _collect_assignment_problem(self) -> Tuple[List[Packet], List[NetworkLink]]:
        """
        Construye el problema de asignación global del instante actual:
        N paquetes pendientes (los primeros de cada cola, que son los únicos que el
        nodo puede despachar durante el próximo Delta t) frente a M enlaces operativos.
        """
        pending: List[Packet] = []
        links: List[NetworkLink] = []

        for node_id, outgoing_links in self.links_by_source.items():
            node = self.nodes[node_id]
            if node.is_egress or not node.buffer:
                continue

            active_links = [lnk for lnk in outgoing_links if lnk.is_active]
            if not active_links:
                continue

            links.extend(active_links)
            # Solo se asignan tantos paquetes por nodo como enlaces de salida tenga:
            # la asignación es 1 a 1 y el resto no llegaría a usarse dentro de Delta t.
            pending.extend(list(node.buffer)[:len(active_links)])

        return pending, links

    def _hungarian_routing_process(self):
        """
        Proceso periódico que ejecuta el Algoritmo Húngaro cada Delta t (HUNGARIAN_INTERVAL)
        sobre el problema global de la red: todos los paquetes en cabeza de cola frente a
        todos los enlaces operativos. Cada asignación queda vigente durante Delta t; pasada
        esa ventana el nodo vuelve a decidir por costo mínimo, porque la foto de saturación
        con la que se resolvió la matriz ya caducó.
        """
        while self._is_running:
            yield self.env.timeout(HUNGARIAN_INTERVAL)

            pending_pkts, candidate_links = self._collect_assignment_problem()
            if not pending_pkts or not candidate_links:
                self.last_assignment_info = {"status": "EMPTY", "assigned_count": 0}
                continue

            assignments, diag = solve_hungarian_assignment(
                pending_packets=pending_pkts,
                candidate_links=candidate_links,
                nodes_dict=self.nodes,
                alpha=ALPHA_SATURATION_WEIGHT,
                feasible=self._is_feasible_pair
            )

            expiry = self.env.now + HUNGARIAN_INTERVAL
            for pkt, chosen_link in assignments:
                pkt.assigned_link_id = chosen_link.link_id
                pkt.assignment_expiry = expiry

            self.last_assignment_info = diag

    def _router_service_process(self, node: RouterNode):
        """
        Proceso de atención de paquetes en cada router.
        Distribución exponencial de tasa mu para el tiempo de procesamiento/servicio.

        El paquete abandona la cola al INICIAR el servicio: así Wq mide únicamente
        espera en cola (y Lq cuenta solo a los que esperan), tal como exige la
        separación entre W = Wq + 1/mu de la teoría de líneas de espera.
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

                # Extracción del buffer ANTES del servicio
                packet = node.dequeue_packet(self.env.now)
                if packet is None:
                    continue
                self.metrics.record_packet_dequeue(self.env.now)

                # Tiempo de servicio exponencial con tasa mu
                mu = max(1.0, self.current_mu)
                service_duration = random.expovariate(mu)
                packet.add_service_time(service_duration)
                yield self.env.timeout(service_duration)

                # Enlace de reenvío decidido al finalizar el servicio
                chosen_link = self._select_output_link(node, packet)
                if chosen_link is None:
                    # Contrapresión: sin ruta operativa hacia el destino o vecino con el
                    # canal cerrado por (s, Q). El paquete regresa al frente del buffer.
                    node.requeue_front(packet, self.env.now)
                    self.metrics.record_packet_enqueue(self.env.now)
                    yield self.env.timeout(BACKPRESSURE_RETRY_DELAY)
                    continue

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

        # La asignación del Húngaro se consume al usarse
        packet.assigned_link_id = None
        packet.assignment_expiry = -1.0

        # Si el enlace se cayó en pleno tránsito, el paquete se pierde.
        # No es un desbordamiento de buffer: se contabiliza como pérdida por falla de enlace.
        if not link.is_active:
            self.metrics.record_packet_lost_in_transit(self.env.now)
            with self._packets_lock:
                self.active_packets.pop(packet.packet_id, None)
            return

        # Si llegó a un nodo de salida (Egress)
        if tgt_node.is_egress:
            packet.mark_completed(self.env.now, egress_id=tgt_node.node_id)
            self.metrics.record_packet_completed(
                now=self.env.now,
                total_wait_time=packet.total_queue_wait_time,
                total_system_time=packet.total_system_time,
                misrouted=packet.was_misrouted
            )
            with self._packets_lock:
                self.active_packets.pop(packet.packet_id, None)
        else:
            # Encolar en el siguiente nodo intermedio
            result = tgt_node.enqueue_packet(packet, self.env.now)
            self._record_admission(packet, result)

    # ========================================================
    # Hilo worker y sincronización con la GUI
    # ========================================================

    def _accumulate_parameter_profile(self, dt: float) -> None:
        """
        Integra lambda y mu en el tiempo para poder reportar el valor medio ponderado
        que realmente rigió la corrida, y no solo el último valor ajustado en la GUI.
        """
        if dt <= 0.0:
            return
        self._lambda_time_integral += self.current_lambda * dt
        self._mu_time_integral += self.current_mu * dt
        self._parameter_elapsed += dt
        self._lambda_min = min(self._lambda_min, self.current_lambda)
        self._lambda_max = max(self._lambda_max, self.current_lambda)
        self._mu_min = min(self._mu_min, self.current_mu)
        self._mu_max = max(self._mu_max, self.current_mu)

    def get_parameter_profile(self) -> Dict[str, Any]:
        """
        Perfil temporal de los parámetros de la corrida: media ponderada en el tiempo,
        valores inicial y final y rango recorrido. Es lo que debe publicar el reporte
        cuando el usuario ajusta lambda con el teclado durante la sesión.
        """
        elapsed = self._parameter_elapsed
        lambda_mean = (self._lambda_time_integral / elapsed) if elapsed > 0 else self.current_lambda
        mu_mean = (self._mu_time_integral / elapsed) if elapsed > 0 else self.current_mu

        return {
            "elapsed": elapsed,
            "lambda_mean": lambda_mean,
            "lambda_initial": self.initial_lambda,
            "lambda_final": self.current_lambda,
            "lambda_min": self._lambda_min,
            "lambda_max": self._lambda_max,
            "lambda_varied": (self._lambda_max - self._lambda_min) > 1e-9,
            "mu_mean": mu_mean,
            "mu_initial": self.initial_mu,
            "mu_final": self.current_mu,
            "mu_min": self._mu_min,
            "mu_max": self._mu_max,
            "mu_varied": (self._mu_max - self._mu_min) > 1e-9,
        }

    def get_flow_control_summary(self) -> Dict[str, Any]:
        """Agrega los contadores de la política (s, Q) de todos los nodos."""
        return {
            "flow_control_signals": sum(n.total_replenish_signals for n in self.nodes.values()),
            "batches_granted": sum(n.total_batches_granted for n in self.nodes.values()),
            "flow_control_blocks": sum(n.total_flow_control_blocks for n in self.nodes.values()),
            "nodes_channel_open": sum(1 for n in self.nodes.values() if n.has_admission_credit()),
            "capacity_S": max((n.capacity_S for n in self.nodes.values()), default=DEFAULT_BUFFER_CAPACITY_S),
            "threshold_s": max((n.threshold_s for n in self.nodes.values()), default=DEFAULT_REORDER_POINT_S),
            "batch_Q": max((n.batch_Q for n in self.nodes.values()), default=DEFAULT_ORDER_BATCH_Q),
        }

    def _run_loop(self) -> None:
        """
        Loop continuo del worker thread:
        Sincroniza el tiempo discreto de SimPy con el tiempo real de pared
        y publica snapshots hacia el puente thread-safe.
        """
        last_wall_time = time.time()
        sim_step = 0.01
        consecutive_errors = 0

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
                        # La topología operativa cambió: recalcular rutas viables
                        self._rebuild_reachability()
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
            time_before = self.env.now
            target_time = time_before + min(0.1, max(sim_step, dt_wall))
            try:
                self.env.run(until=target_time)
                consecutive_errors = 0
            except Exception as ex:
                # Nunca silenciar un fallo del motor: sin traza la simulación
                # seguiría publicando snapshots vacíos como si todo marchara bien.
                consecutive_errors += 1
                self.engine_errors += 1
                self.last_engine_error = f"{type(ex).__name__}: {ex}"
                print(f"[ENGINE][ERROR] Fallo en env.run(until={target_time:.3f}): {self.last_engine_error}")
                traceback.print_exc()
                if consecutive_errors >= MAX_ENGINE_ERRORS:
                    print(
                        f"[ENGINE][ERROR] {consecutive_errors} fallos consecutivos: "
                        "se aborta la simulación para no reportar métricas inválidas."
                    )
                    self._is_running = False

            self._accumulate_parameter_profile(self.env.now - time_before)

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
                "batch_credits": n.remaining_batch_credits,
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

        flow_summary = self.get_flow_control_summary()

        snapshot = {
            "sim_time": sim_now,
            "lambda": self.current_lambda,
            "mu": self.current_mu,
            "metrics": metrics_snap,
            "nodes": nodes_state,
            "links": links_state,
            "packets": packets_state,
            "params": {
                "capacity_S": flow_summary["capacity_S"],
                "threshold_s": flow_summary["threshold_s"],
                "batch_Q": flow_summary["batch_Q"],
                "alpha": ALPHA_SATURATION_WEIGHT,
                "hungarian_interval": HUNGARIAN_INTERVAL,
            },
            "flow_control": flow_summary,
            "lambda_profile": self.get_parameter_profile(),
            "assignment": self.last_assignment_info,
            "engine_errors": self.engine_errors,
            "last_engine_error": self.last_engine_error,
        }

        self.bridge.publish_snapshot(snapshot)

    def stop(self) -> Dict[str, Any]:
        """
        Detiene la simulación y retorna las métricas finales, enriquecidas con el
        perfil temporal de lambda/mu y el resumen de la política (s, Q) para que el
        reporte describa la corrida tal como ocurrió.
        """
        self._is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

        final_metrics = self.metrics.get_metrics_snapshot(self.env.now)
        final_metrics["lambda_profile"] = self.get_parameter_profile()
        final_metrics["flow_control"] = self.get_flow_control_summary()
        final_metrics["engine_errors"] = self.engine_errors
        final_metrics["last_engine_error"] = self.last_engine_error
        return final_metrics
