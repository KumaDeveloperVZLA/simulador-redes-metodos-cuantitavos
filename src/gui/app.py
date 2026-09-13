"""
Aplicación Principal de GUI con Pygame.
Gestiona el Game Loop a 60 FPS, eventos de entrada (teclado/mouse), renderizado en tiempo real
y disparo del proceso de exportación y análisis.
"""

import os
import sys
import time
import pygame
from typing import Optional, Dict, Any

from ..config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    CANVAS_WIDTH,
    FPS,
    DEFAULT_LAMBDA,
    DEFAULT_MU,
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q
)
from ..simulation.bridge import SimulationBridge
from ..simulation.engine import NetworkSimulationEngine
from .renderer import NetworkRenderer
from .hud import SimulationHUD
from ..reporting.exporter import export_simulation_report
from ..reporting.api_client import request_ai_analysis
from ..reporting.doc_generator import generate_technical_docx_report


class NetworkSimulatorApp:
    """
    Controlador principal de la ventana interactiva Pygame.
    """

    def __init__(
        self,
        initial_lambda: float = DEFAULT_LAMBDA,
        initial_mu: float = DEFAULT_MU,
        output_report_path: str = "reporte_simulacion.txt",
        output_docx_path: str = "informe_tecnico.docx"
    ):
        pygame.init()
        pygame.display.set_caption("Simulador Dinámico de Redes de Computadoras | UJAP")

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.is_running = True

        self.output_report_path = output_report_path
        self.output_docx_path = output_docx_path

        # Inicialización de tipografías modernas
        self._init_fonts()

        # Componentes de Simulación
        self.bridge = SimulationBridge(initial_lambda=initial_lambda, initial_mu=initial_mu)
        self.engine = NetworkSimulationEngine(
            bridge=self.bridge,
            initial_lambda=initial_lambda,
            initial_mu=initial_mu
        )

        # Componentes Gráficos
        self.renderer = NetworkRenderer(
            surface=self.screen,
            font_bold=self.font_bold,
            font_regular=self.font_regular,
            font_small=self.font_small
        )
        self.hud = SimulationHUD(
            surface=self.screen,
            font_title=self.font_title,
            font_bold=self.font_bold,
            font_regular=self.font_regular,
            font_small=self.font_small
        )

        # Control de captura de pantalla automática para el informe
        self.screenshot_taken = False
        self.screenshot_path = os.path.join("assets", "screenshot_simulator.png")

    def _init_fonts(self) -> None:
        """Carga fuentes del sistema con fallback elegante."""
        try:
            # Buscar fuentes estilizadas sans-serif
            self.font_title = pygame.font.SysFont("Segoe UI", 20, bold=True)
            self.font_bold = pygame.font.SysFont("Segoe UI", 14, bold=True)
            self.font_regular = pygame.font.SysFont("Segoe UI", 13)
            self.font_small = pygame.font.SysFont("Segoe UI", 11)
        except Exception:
            self.font_title = pygame.font.Font(None, 24)
            self.font_bold = pygame.font.Font(None, 18)
            self.font_regular = pygame.font.Font(None, 16)
            self.font_small = pygame.font.Font(None, 14)

    def run(self) -> None:
        """Ejecuta el bucle principal de la aplicación gráfica."""
        # Arrancar motor de simulación SimPy en hilo worker
        self.engine.start()
        print("[APP] Simulador iniciado. Presiona ESPACIO para pausar, +/- para cambiar lambda, click en enlace para simular falla, E/ESC para finalizar.")

        start_time = time.time()

        try:
            while self.is_running:
                mouse_pos = pygame.mouse.get_pos()

                # 1. Manejo de Eventos
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.is_running = False

                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_ESCAPE, pygame.K_e):
                            print("[APP] Señal de finalización recibida.")
                            self.is_running = False

                        elif event.key == pygame.K_SPACE:
                            is_p = self.bridge.toggle_pause()
                            print(f"[APP] Simulación {'PAUSADA' if is_p else 'REANUDADA'}.")

                        elif event.key in (pygame.K_UP, pygame.K_PLUS, pygame.K_KP_PLUS):
                            new_lam = self.bridge.adjust_lambda(1.0)
                            print(f"[APP] Lambda incrementada a: {new_lam:.1f} pkt/s")

                        elif event.key in (pygame.K_DOWN, pygame.K_MINUS, pygame.K_KP_MINUS):
                            new_lam = self.bridge.adjust_lambda(-1.0)
                            print(f"[APP] Lambda reducida a: {new_lam:.1f} pkt/s")

                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        # Verificar si el click fue en un botón del HUD
                        action = self.hud.handle_click(mouse_pos)
                        if action == "toggle_pause":
                            self.bridge.toggle_pause()
                        elif action == "lambda_plus":
                            self.bridge.adjust_lambda(1.0)
                        elif action == "lambda_minus":
                            self.bridge.adjust_lambda(-1.0)
                        elif action == "stop_export":
                            self.is_running = False
                        else:
                            # Verificar si se hizo click sobre algún enlace de la red
                            if mouse_pos[0] < CANVAS_WIDTH:
                                snap = self.bridge.get_snapshot()
                                clicked_link = self.renderer.find_clicked_link(mouse_pos, snap.get("links", []))
                                if clicked_link:
                                    self.bridge.toggle_link(clicked_link)
                                    print(f"[APP] Enlace '{clicked_link}' alternado (Fallo / Operativo).")

                # 2. Obtener último estado sincronizado
                snapshot = self.bridge.get_snapshot()

                # 3. Renderizado de capas
                # Fondo y cuadrícula
                self.renderer.draw_canvas_grid(CANVAS_WIDTH, SCREEN_HEIGHT)

                # Enlaces dinámicos
                self.renderer.draw_links(snapshot.get("links", []))

                # Nodos con anillos cromáticos de saturación
                self.renderer.draw_nodes(snapshot.get("nodes", []))

                # Paquetes animados viajando interpoladamente (LERP)
                self.renderer.draw_packets(snapshot.get("packets", []))

                # Panel lateral HUD
                self.hud.draw(snapshot, mouse_pos)

                # Tomar captura automática a los 3 segundos de simulación para el informe docx
                elapsed = time.time() - start_time
                if not self.screenshot_taken and elapsed > 3.0 and snapshot.get("sim_time", 0.0) > 2.0:
                    self.save_screenshot(self.screenshot_path)
                    self.screenshot_taken = True

                # Actualizar pantalla
                pygame.display.flip()
                self.clock.tick(FPS)

        finally:
            self._shutdown_and_export()

    def save_screenshot(self, filename: str) -> None:
        """Guarda una captura de la interfaz para incluir en el informe."""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            pygame.image.save(self.screen, filename)
            print(f"[APP] Captura de pantalla guardada en: {filename}")
        except Exception as ex:
            print(f"[APP] No se pudo guardar la captura: {ex}")

    def _shutdown_and_export(self) -> None:
        """Finaliza los hilos, guarda reporte, llama API y genera el informe docx."""
        print("[APP] Deteniendo motor de simulación...")
        # Si no se tomó captura durante la corrida, tomar una antes de salir
        if not self.screenshot_taken:
            self.save_screenshot(self.screenshot_path)
            self.screenshot_taken = True

        final_metrics = self.engine.stop()
        final_time = final_metrics.get("simulation_time", 0.0)

        # Lambda y mu que REALMENTE rigieron la corrida: si el usuario los ajustó con
        # el teclado durante la sesión, el último valor del puente no describe la
        # simulación y dejaría el reporte internamente contradictorio.
        profile = final_metrics.get("lambda_profile", {})
        flow_summary = final_metrics.get("flow_control", {})
        effective_lambda = profile.get("lambda_mean", DEFAULT_LAMBDA)
        effective_mu = profile.get("mu_mean", DEFAULT_MU)

        if profile.get("lambda_varied"):
            print(
                f"[APP] Lambda varió durante la corrida "
                f"({profile.get('lambda_initial', 0.0):.1f} -> {profile.get('lambda_final', 0.0):.1f} pkt/s). "
                f"Se reporta la media ponderada en el tiempo: {effective_lambda:.2f} pkt/s."
            )

        # 1. Exportar reporte TXT estricto
        print(f"[APP] Exportando reporte a: {self.output_report_path}")
        report_text = export_simulation_report(
            filepath=self.output_report_path,
            sim_time=final_time,
            lambda_val=effective_lambda,
            mu_val=effective_mu,
            capacity_S=flow_summary.get("capacity_S", DEFAULT_BUFFER_CAPACITY_S),
            threshold_s=flow_summary.get("threshold_s", DEFAULT_REORDER_POINT_S),
            metrics=final_metrics,
            batch_Q=flow_summary.get("batch_Q", DEFAULT_ORDER_BATCH_Q),
            lambda_profile=profile
        )

        # 2. Llamada HTTP a la API Externa para análisis automatizado
        print("[APP] Solicitando diagnóstico automatizado a la API...")
        api_response = request_ai_analysis(
            report_content=report_text,
            metrics=final_metrics,
            report_file_path=self.output_report_path
        )

        # 3. Generación del Informe Técnico en Word (.docx)
        print(f"[APP] Generando Informe Técnico en: {self.output_docx_path}")
        generate_technical_docx_report(
            docx_path=self.output_docx_path,
            metrics=final_metrics,
            sim_time=final_time,
            lambda_val=effective_lambda,
            mu_val=effective_mu,
            api_analysis=api_response,
            screenshot_image_path=self.screenshot_path,
            lambda_profile=profile
        )

        pygame.quit()
        print("[APP] Proceso completado exitosamente. Todos los entregables han sido generados.")
