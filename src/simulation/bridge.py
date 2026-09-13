"""
Puente de Sincronización Desacoplado SimPy ↔ Pygame.
Permite la comunicación bidireccional y thread-safe entre el motor de eventos discretos
y el game loop de Pygame a 60 FPS, evitando bloqueos de GUI.
"""

import threading
from typing import Dict, Any, List, Optional
from queue import Queue

from ..config import (
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q,
    ALPHA_SATURATION_WEIGHT,
    HUNGARIAN_INTERVAL
)


class SimulationBridge:
    """
    Estructura desacoplada y thread-safe para sincronización de estados y comandos.
    """

    def __init__(self, initial_lambda: float, initial_mu: float):
        self._lock = threading.Lock()

        # Parámetros dinámicos controlados por el usuario
        self._current_lambda: float = initial_lambda
        self._current_mu: float = initial_mu
        self._is_paused: bool = False
        self._is_stopped: bool = False

        # Cola de comandos desde la GUI hacia SimPy
        self._ui_command_queue: Queue = Queue()

        # Último snapshot de estado para renderizado en Pygame
        self._latest_snapshot: Dict[str, Any] = {
            "sim_time": 0.0,
            "lambda": initial_lambda,
            "mu": initial_mu,
            "is_paused": False,
            "is_stopped": False,
            "metrics": {
                "L_q": 0.0,
                "L": 0.0,
                "W_q": 0.0,
                "W": 0.0,
                "total_generated": 0,
                "total_processed": 0,
                "total_dropped": 0,
                "loss_rate_pct": 0.0,
                "holding_cost": 0.0,
                "shortage_cost": 0.0,
                "global_cost": 0.0,
            },
            "nodes": [],
            "links": [],
            "packets": [],
            "recent_events": [],
            "params": {
                "capacity_S": DEFAULT_BUFFER_CAPACITY_S,
                "threshold_s": DEFAULT_REORDER_POINT_S,
                "batch_Q": DEFAULT_ORDER_BATCH_Q,
                "alpha": ALPHA_SATURATION_WEIGHT,
                "hungarian_interval": HUNGARIAN_INTERVAL,
            },
            "flow_control": {
                "flow_control_signals": 0,
                "batches_granted": 0,
                "flow_control_blocks": 0,
            },
            "lambda_profile": {
                "lambda_mean": initial_lambda,
                "lambda_initial": initial_lambda,
                "lambda_final": initial_lambda,
                "lambda_min": initial_lambda,
                "lambda_max": initial_lambda,
                "lambda_varied": False,
            },
        }

    # ====================================================
    # Métodos invocados por la GUI (Pygame Main Thread)
    # ====================================================

    def get_snapshot(self) -> Dict[str, Any]:
        """Obtiene una copia segura del último estado publicado."""
        with self._lock:
            # Retorna referencia al diccionario de snapshot
            return self._latest_snapshot

    def toggle_pause(self) -> bool:
        """Pausa o reanuda la simulación sin congelar el hilo de renderizado."""
        with self._lock:
            self._is_paused = not self._is_paused
            current_paused = self._is_paused
        self._ui_command_queue.put({"action": "SET_PAUSE", "value": current_paused})
        return current_paused

    def adjust_lambda(self, delta: float) -> float:
        """Aumenta o disminuye la tasa de llegada lambda."""
        with self._lock:
            self._current_lambda = max(1.0, min(100.0, self._current_lambda + delta))
            new_val = self._current_lambda
        self._ui_command_queue.put({"action": "SET_LAMBDA", "value": new_val})
        return new_val

    def set_lambda(self, value: float) -> float:
        """Asigna directamente un nuevo valor a lambda."""
        with self._lock:
            self._current_lambda = max(1.0, min(100.0, value))
            new_val = self._current_lambda
        self._ui_command_queue.put({"action": "SET_LAMBDA", "value": new_val})
        return new_val

    def toggle_link(self, link_id: str) -> None:
        """Solicita alternar el estado operativo de un enlace."""
        self._ui_command_queue.put({"action": "TOGGLE_LINK", "link_id": link_id})

    def request_stop(self) -> None:
        """Solicita detener la simulación de manera ordenada."""
        with self._lock:
            self._is_stopped = True
        self._ui_command_queue.put({"action": "STOP"})

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._is_paused

    @property
    def is_stopped(self) -> bool:
        with self._lock:
            return self._is_stopped

    # ====================================================
    # Métodos invocados por el Motor (SimPy Worker Thread)
    # ====================================================

    def poll_commands(self) -> List[Dict[str, Any]]:
        """Extrae todos los comandos pendientes enviados desde la GUI."""
        commands = []
        while not self._ui_command_queue.empty():
            commands.append(self._ui_command_queue.get_nowait())
        return commands

    def publish_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Publica de forma thread-safe un nuevo estado consolidado para la GUI."""
        with self._lock:
            snapshot["is_paused"] = self._is_paused
            snapshot["is_stopped"] = self._is_stopped
            snapshot["lambda"] = self._current_lambda
            snapshot["mu"] = self._current_mu
            self._latest_snapshot = snapshot
