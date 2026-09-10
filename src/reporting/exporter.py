"""
Generador del Reporte Estructurado de Simulación de Red (reporte_simulacion.txt).
Respeta estrictamente el formato exigido en INSTRUCCIONES.md y ejercicio.md.
"""

import os
from typing import Dict, Any


def format_simulation_report(
    sim_time: float,
    lambda_val: float,
    mu_val: float,
    capacity_S: int,
    threshold_s: int,
    metrics: Dict[str, Any]
) -> str:
    """
    Construye la cadena de texto con el formato exacto requerido:
    ==================================================
               REPORTE DE SIMULACIÓN DE RED           
    ==================================================
    Tiempo Total de Simulación: [T] s
    Tasa de Llegada (lambda): [λ] paquetes/s
    Tasa de Servicio (mu): [μ] paquetes/s
    Capacidad de Buffer (S): [S] paquetes
    Umbral Reabastecimiento (s): [s] paquetes
    --------------------------------------------------
    METRICAS OBTENIDAS:
    Paquetes Procesados: [N_proc]
    Paquetes Perdidos (Overflow): [N_loss]
    Tasa de Pérdida: [X.XX]%
    Tiempo Medio en Cola (Wq): [X.XX] s
    Promedio Paquetes en Sistema (L): [X.XX]
    Costo Total de Almacenamiento: $[X.XX]
    Costo Total de Penalización (Ruptura): $[X.XX]
    --------------------------------------------------
    Costo Global del Sistema: $[X.XX]
    ==================================================
    """
    n_proc = metrics.get("total_processed", 0)
    n_loss = metrics.get("total_dropped", 0)
    loss_pct = metrics.get("loss_rate_pct", 0.0)
    wq = metrics.get("W_q", 0.0)
    l_val = metrics.get("L", 0.0)
    c_hold = metrics.get("holding_cost", 0.0)
    c_short = metrics.get("shortage_cost", 0.0)
    c_global = metrics.get("global_cost", 0.0)

    report_lines = [
        "=" * 50,
        "           REPORTE DE SIMULACIÓN DE RED           ",
        "=" * 50,
        f"Tiempo Total de Simulación: {sim_time:.1f} s",
        f"Tasa de Llegada (lambda): {lambda_val:.1f} paquetes/s",
        f"Tasa de Servicio (mu): {mu_val:.1f} paquetes/s",
        f"Capacidad de Buffer (S): {capacity_S} paquetes",
        f"Umbral Reabastecimiento (s): {threshold_s} paquetes",
        "-" * 50,
        "METRICAS OBTENIDAS:",
        f"Paquetes Procesados: {n_proc}",
        f"Paquetes Perdidos (Overflow): {n_loss}",
        f"Tasa de Pérdida: {loss_pct:.2f}%",
        f"Tiempo Medio en Cola (Wq): {wq:.2f} s",
        f"Promedio Paquetes en Sistema (L): {l_val:.2f}",
        f"Costo Total de Almacenamiento: ${c_hold:.2f}",
        f"Costo Total de Penalización (Ruptura): ${c_short:.2f}",
        "-" * 50,
        f"Costo Global del Sistema: ${c_global:.2f}",
        "=" * 50,
    ]

    return "\n".join(report_lines) + "\n"


def export_simulation_report(
    filepath: str,
    sim_time: float,
    lambda_val: float,
    mu_val: float,
    capacity_S: int,
    threshold_s: int,
    metrics: Dict[str, Any]
) -> str:
    """
    Escribe el reporte en disco en la ruta especificada y retorna el texto generado.
    """
    content = format_simulation_report(
        sim_time=sim_time,
        lambda_val=lambda_val,
        mu_val=mu_val,
        capacity_S=capacity_S,
        threshold_s=threshold_s,
        metrics=metrics
    )

    # Asegurar directorio
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return content
