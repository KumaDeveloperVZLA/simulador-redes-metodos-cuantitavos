"""
Punto de Entrada Principal del Proyecto:
Simulador Dinámico de Redes de Computadoras
Universidad José Antonio Páez - Métodos Cuantitativos

Uso:
  # Modo Interactivo con GUI Pygame a 60 FPS:
  python main.py

  # Modo Headless / Corrida de Evaluación Directa:
  python main.py --headless --duration 30
"""

import sys
import os
import time
import argparse
from typing import Dict, Any

# Configurar salida de consola segura en Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Cargar variables de entorno desde .env si existe
from dotenv import load_dotenv
load_dotenv()

from src.config import (
    DEFAULT_LAMBDA,
    DEFAULT_MU,
    DEFAULT_BUFFER_CAPACITY_S,
    DEFAULT_REORDER_POINT_S,
    DEFAULT_ORDER_BATCH_Q,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    CANVAS_WIDTH
)
from src.simulation.bridge import SimulationBridge
from src.simulation.engine import NetworkSimulationEngine
from src.reporting.exporter import export_simulation_report
from src.reporting.api_client import request_ai_analysis
from src.reporting.doc_generator import generate_technical_docx_report


def run_headless_simulation(
    duration: float = 30.0,
    lambd: float = DEFAULT_LAMBDA,
    mu: float = DEFAULT_MU,
    report_path: str = "reporte_simulacion.txt",
    docx_path: str = "informe_tecnico.docx"
) -> None:
    """
    Ejecuta una corrida de simulación completa en modo headless (sin abrir ventana gráfica),
    ideal para pruebas automatizadas, compilación de métricas y generación de entregables.
    """
    print(f"\n=======================================================")
    print(f"  EJECUTANDO SIMULACION HEADLESS ({duration:.1f} s)")
    print(f"  lambda = {lambd:.1f} pkt/s | mu = {mu:.1f} pkt/s")
    print(f"=======================================================\n")

    bridge = SimulationBridge(initial_lambda=lambd, initial_mu=mu)
    engine = NetworkSimulationEngine(bridge=bridge, initial_lambda=lambd, initial_mu=mu)
    engine.start()

    start_wall = time.time()
    last_print = 0.0

    while True:
        snap = bridge.get_snapshot()
        sim_time = snap.get("sim_time", 0.0)

        # Imprimir progreso cada 5 segundos
        if sim_time - last_print >= 5.0 or sim_time >= duration:
            m = snap.get("metrics", {})
            print(
                f"[SIM] T: {sim_time:04.1f}s | Procesados: {m.get('total_processed', 0)} | "
                f"Perdidos: {m.get('total_dropped', 0)} ({m.get('loss_rate_pct', 0.0):.1f}%) | "
                f"L: {m.get('L', 0.0):.2f} | Wq: {m.get('W_q', 0.0):.3f}s | "
                f"Costo: ${m.get('global_cost', 0.0):.2f}"
            )
            last_print = sim_time

        if sim_time >= duration:
            break

        # Si el motor abortó por fallos repetidos, el reloj de simulación deja de
        # avanzar: hay que salir con lo recolectado en vez de esperar indefinidamente.
        if not engine.is_running:
            print(
                f"[SIM] El motor se detuvo antes de completar la corrida "
                f"(T = {sim_time:.1f}s de {duration:.1f}s). Se reportará lo recolectado."
            )
            break

        time.sleep(0.1)

    print("\n[SIM] Finalizando motor de simulación y recolectando métricas...")
    final_metrics = engine.stop()
    final_time = final_metrics.get("simulation_time", duration)

    # Parámetros efectivos de la corrida (media ponderada en el tiempo)
    profile = final_metrics.get("lambda_profile", {})
    flow_summary = final_metrics.get("flow_control", {})
    effective_lambda = profile.get("lambda_mean", lambd)
    effective_mu = profile.get("mu_mean", mu)

    # 1. Exportar reporte TXT
    print(f"[REPORTE] Guardando reporte formal en: {report_path}")
    report_text = export_simulation_report(
        filepath=report_path,
        sim_time=final_time,
        lambda_val=effective_lambda,
        mu_val=effective_mu,
        capacity_S=flow_summary.get("capacity_S", DEFAULT_BUFFER_CAPACITY_S),
        threshold_s=flow_summary.get("threshold_s", DEFAULT_REORDER_POINT_S),
        metrics=final_metrics,
        batch_Q=flow_summary.get("batch_Q", DEFAULT_ORDER_BATCH_Q),
        lambda_profile=profile
    )

    # 2. Análisis vía API HTTP
    print("[API] Solicitando diagnóstico automatizado a la API...")
    api_diag = request_ai_analysis(
        report_content=report_text,
        metrics=final_metrics,
        report_file_path=report_path
    )

    # 3. Generar captura esquemática de la topología para el documento Word
    screenshot_path = os.path.join("assets", "screenshot_simulator.png")
    _generate_offline_topology_image(screenshot_path, snap)

    # 4. Generar Informe Técnico en Word (.docx)
    print(f"[DOCX] Generando Informe Técnico formal en: {docx_path}")
    generate_technical_docx_report(
        docx_path=docx_path,
        metrics=final_metrics,
        sim_time=final_time,
        lambda_val=effective_lambda,
        mu_val=effective_mu,
        api_analysis=api_diag,
        screenshot_image_path=screenshot_path,
        lambda_profile=profile
    )

    print("\n=======================================================")
    print("  SIMULACIÓN FINALIZADA CON ÉXITO")
    print(f"  1. Reporte TXT: {os.path.abspath(report_path)}")
    print(f"  2. Informe DOCX: {os.path.abspath(docx_path)}")
    print("=======================================================\n")


def _generate_offline_topology_image(image_path: str, snapshot: Dict[str, Any]) -> None:
    """Genera una imagen gráfica nítida de la red para el informe usando Pygame o Matplotlib."""
    try:
        import pygame
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        font_bold = pygame.font.SysFont("Segoe UI", 14, bold=True)
        font_reg = pygame.font.SysFont("Segoe UI", 13)
        font_sm = pygame.font.SysFont("Segoe UI", 11)

        from src.gui.renderer import NetworkRenderer
        from src.gui.hud import SimulationHUD

        renderer = NetworkRenderer(surf, font_bold, font_reg, font_sm)
        hud = SimulationHUD(surf, font_bold, font_bold, font_reg, font_sm)

        renderer.draw_canvas_grid(CANVAS_WIDTH, SCREEN_HEIGHT)
        renderer.draw_links(snapshot.get("links", []))
        renderer.draw_nodes(snapshot.get("nodes", []))
        renderer.draw_packets(snapshot.get("packets", []))
        hud.draw(snapshot, (0, 0))

        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        pygame.image.save(surf, image_path)
        pygame.quit()
        print(f"[IMAGEN] Captura de topología guardada en: {image_path}")
    except Exception as ex:
        print(f"[IMAGEN] Fallback generación visual: {ex}")


def main():
    parser = argparse.ArgumentParser(
        description="Simulador Dinámico de Redes de Computadoras | UJAP Métodos Cuantitativos"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar en modo headless sin ventana gráfica (ideal para pruebas y compilación de entregables)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Duración en segundos para la simulación headless (por defecto: 30s)"
    )
    parser.add_argument(
        "--lambda_rate",
        type=float,
        default=DEFAULT_LAMBDA,
        help=f"Tasa de llegada de Poisson (por defecto: {DEFAULT_LAMBDA} pkt/s)"
    )
    parser.add_argument(
        "--mu_rate",
        type=float,
        default=DEFAULT_MU,
        help=f"Tasa de servicio exponencial (por defecto: {DEFAULT_MU} pkt/s)"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="reporte_simulacion.txt",
        help="Ruta del archivo de texto de salida (por defecto: reporte_simulacion.txt)"
    )
    parser.add_argument(
        "--docx",
        type=str,
        default="informe_tecnico.docx",
        help="Ruta del informe técnico en Word (por defecto: informe_tecnico.docx)"
    )

    args = parser.parse_args()

    if args.headless:
        run_headless_simulation(
            duration=args.duration,
            lambd=args.lambda_rate,
            mu=args.mu_rate,
            report_path=args.report,
            docx_path=args.docx
        )
    else:
        # Modo interactivo con GUI Pygame
        from src.gui.app import NetworkSimulatorApp
        app = NetworkSimulatorApp(
            initial_lambda=args.lambda_rate,
            initial_mu=args.mu_rate,
            output_report_path=args.report,
            output_docx_path=args.docx
        )
        app.run()


if __name__ == "__main__":
    main()
